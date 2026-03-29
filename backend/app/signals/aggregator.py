"""Signal Aggregator - combines raw signals into composite trading signals."""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog

logger = structlog.get_logger(__name__)

from app.config.constants import (
    ATR_MULTIPLIER_DEFAULT,
    ATR_MULTIPLIER_LOW_VOL,
    ATR_MULTIPLIER_RANGING,
    ATR_MULTIPLIER_TRENDING,
    ATR_MULTIPLIER_VOLATILE,
    Direction,
    EventChannel,
    GRADE_RISK_MULTIPLIER,
    HIGHER_TF_MAP,
    MTF_ALIGNMENT_BOOST,
    MTF_MISALIGNMENT_PENALTY,
    MarketRegime,
    MAX_RISK_PER_TRADE,
    MIN_STRATEGY_AGREEMENT,
    REGIME_POSITION_MULTIPLIER,
    SignalGrade,
    StopLossType,
    TP1_CLOSE_PCT,
    TP1_RR_RATIO,
    TP2_CLOSE_PCT,
    TP2_RR_RATIO,
    TP3_CLOSE_PCT,
    TP3_RR_RATIO,
)
from app.core.events import event_bus
from app.core.models import (
    CompositeSignal,
    EventMessage,
    MarketContext,
    PositionSize,
    RawSignal,
    RiskReward,
    TakeProfit,
)
from app.indicators.base import IndicatorPipeline
from app.signals.regime import MarketRegimeDetector
from app.strategies.base import BaseStrategy

if TYPE_CHECKING:
    from app.data.collector import DataCollector


class SignalAggregator:
    """Aggregates signals from multiple strategies into a CompositeSignal.

    Flow:
    1. Fetch candles from DataCollector
    2. Compute indicators via IndicatorPipeline
    3. Detect market regime
    4. Run all strategies → collect RawSignals
    5. Filter: need >= MIN_STRATEGY_AGREEMENT agreeing on direction
    6. Weight-average strengths → composite strength
    7. Grade: A(>=0.80), B(>=0.60), C(>=0.40), D(<0.40)
    8. Calculate stop loss, take profits, position sizing
    9. Publish CompositeSignal via EventBus
    """

    def __init__(
        self,
        strategies: list[BaseStrategy],
        regime_detector: MarketRegimeDetector | None = None,
    ) -> None:
        self._strategies = strategies
        self._regime_detector = regime_detector or MarketRegimeDetector()
        self._pipeline = IndicatorPipeline()

    async def aggregate(
        self,
        collector: DataCollector,
        symbol: str,
        timeframe: str,
        portfolio_balance: float = 10000.0,
    ) -> CompositeSignal | None:
        """Run all strategies and aggregate into a CompositeSignal.

        Enhanced with:
        - Multi-timeframe confirmation (higher TF trend filter)
        - EMA 200 trend filter (penalize counter-trend signals)
        - Regime-adaptive position sizing (not blocking)
        - Grade-based risk allocation
        - MACD divergence detection
        """
        # 1. Fetch candles for entry timeframe
        max_candles = max(s.min_candles for s in self._strategies)
        candles = await collector.get_candles(
            symbol, timeframe, limit=max(max_candles, 200)
        )
        if not candles:
            return None

        # 2. Compute indicators
        indicators = self._pipeline.compute(candles)

        # 3. Detect regime
        context = self._regime_detector.detect(candles, indicators)

        # 4. Multi-timeframe: fetch higher TF trend direction
        higher_trend = Direction.NEUTRAL
        higher_tf = HIGHER_TF_MAP.get(timeframe)
        if higher_tf and higher_tf != timeframe:
            try:
                htf_candles = await collector.get_candles(symbol, higher_tf, limit=200)
                if htf_candles and len(htf_candles) >= 55:
                    htf_ind = self._pipeline.compute(htf_candles)
                    if htf_ind.ema_9 and htf_ind.ema_21 and htf_ind.ema_55:
                        if htf_ind.ema_9 > htf_ind.ema_21 > htf_ind.ema_55:
                            higher_trend = Direction.LONG
                        elif htf_ind.ema_9 < htf_ind.ema_21 < htf_ind.ema_55:
                            higher_trend = Direction.SHORT
                    logger.debug(
                        "aggregator.higher_tf",
                        symbol=symbol,
                        higher_tf=higher_tf,
                        trend=higher_trend,
                    )
            except Exception:
                pass  # higher TF unavailable — proceed without

        # 5. Pre-fetch async data for strategies that need it
        for strategy in self._strategies:
            try:
                await strategy.prepare(collector, symbol)
            except Exception:
                continue

        # 6. Run strategies
        signals: list[RawSignal] = []
        for strategy in self._strategies:
            try:
                signal = strategy.evaluate(candles, indicators, context)
                if signal is not None:
                    signals.append(signal)
            except Exception:
                continue

        if not signals:
            return None

        # 7. Count direction agreement
        direction_counts = Counter(s.direction for s in signals)
        dominant_dir, dominant_count = direction_counts.most_common(1)[0]

        if dominant_dir == Direction.NEUTRAL:
            return None

        if dominant_count < MIN_STRATEGY_AGREEMENT:
            return None

        # 8. Compute weighted strength
        agreeing = [s for s in signals if s.direction == dominant_dir]
        strategy_weights = {s.name: s.weight for s in self._strategies}

        total_weight = 0.0
        weighted_strength = 0.0
        strategy_scores: dict[str, float] = {}

        for sig in agreeing:
            w = strategy_weights.get(sig.strategy_name, 0.1)
            total_weight += w
            weighted_strength += abs(sig.strength) * w
            strategy_scores[sig.strategy_name] = abs(sig.strength)

        composite_strength = weighted_strength / total_weight if total_weight > 0 else 0.0

        # 9. Multi-timeframe alignment adjustment
        if higher_trend != Direction.NEUTRAL:
            if dominant_dir == higher_trend:
                composite_strength += MTF_ALIGNMENT_BOOST  # Boost aligned signals
                strategy_scores["_mtf_boost"] = MTF_ALIGNMENT_BOOST
            else:
                composite_strength -= MTF_MISALIGNMENT_PENALTY  # Penalize counter-trend
                strategy_scores["_mtf_penalty"] = -MTF_MISALIGNMENT_PENALTY

        # 10. EMA 200 trend filter — penalize counter-trend signals
        close = candles[-1].close
        if indicators.ema_200 and indicators.ema_200 > 0:
            if dominant_dir == Direction.LONG and close < indicators.ema_200:
                composite_strength *= 0.70  # Below EMA200 penalizes longs
                strategy_scores["_ema200_penalty"] = -0.30
            elif dominant_dir == Direction.SHORT and close > indicators.ema_200:
                composite_strength *= 0.70  # Above EMA200 penalizes shorts
                strategy_scores["_ema200_penalty"] = -0.30

        # 11. MACD divergence boost
        macd_div = self._detect_macd_divergence(candles, indicators)
        if macd_div:
            if (macd_div == "bullish" and dominant_dir == Direction.LONG) or \
               (macd_div == "bearish" and dominant_dir == Direction.SHORT):
                composite_strength += 0.10  # Divergence confirms signal
                strategy_scores["_macd_divergence"] = 0.10

        composite_strength = min(1.0, max(0.0, composite_strength))

        # 12. Grade
        grade = self._compute_grade(composite_strength)

        # 13. Grade-based + regime-adaptive risk
        grade_mult = GRADE_RISK_MULTIPLIER.get(grade.value, 0.5)
        regime_mult = REGIME_POSITION_MULTIPLIER.get(context.regime.value, 0.5)

        # D-grade signals: skip entirely
        if grade_mult == 0.0:
            return None

        effective_risk = MAX_RISK_PER_TRADE * grade_mult * regime_mult

        # 14. Calculate risk management
        entry_price = close
        atr = indicators.atr_14 or (entry_price * 0.01)

        stop_loss, sl_type = self._calculate_stop_loss(
            candles, dominant_dir, atr, context.regime
        )
        take_profits = self._calculate_take_profits(
            entry_price, stop_loss, dominant_dir
        )
        risk_reward = self._calculate_risk_reward(
            entry_price, stop_loss, take_profits
        )
        position_size = self._calculate_position_size(
            entry_price, stop_loss, portfolio_balance, effective_risk
        )

        # Entry zone: +/- 0.5 ATR
        half_atr = atr * 0.5
        if dominant_dir == Direction.LONG:
            entry_zone = (entry_price - half_atr, entry_price)
        else:
            entry_zone = (entry_price, entry_price + half_atr)

        composite = CompositeSignal(
            symbol=symbol,
            direction=dominant_dir,
            grade=grade,
            strength=composite_strength,
            entry_price=entry_price,
            entry_zone=entry_zone,
            stop_loss=stop_loss,
            sl_type=sl_type,
            take_profits=take_profits,
            risk_reward=risk_reward,
            position_size=position_size,
            strategy_scores=strategy_scores,
            market_context=context,
        )

        # 15. Publish
        try:
            await event_bus.publish(
                EventChannel.SIGNAL_COMPOSITE,
                EventMessage(
                    event_type="composite_signal",
                    data=composite.model_dump(mode="json"),
                ),
            )
        except Exception as exc:
            logger.debug("aggregator.publish_failed", error=str(exc))

        return composite

    @staticmethod
    def _detect_macd_divergence(candles: list, indicators) -> str | None:
        """Detect MACD divergence over recent candles.

        Bullish divergence: price makes lower low, MACD histogram makes higher low
        Bearish divergence: price makes higher high, MACD histogram makes lower high
        Returns: "bullish" | "bearish" | None
        """
        if len(candles) < 20 or not indicators.macd_histogram:
            return None

        # Compare last 14 candles in two halves
        mid = len(candles) - 7
        recent_lows = [c.low for c in candles[-7:]]
        prior_lows = [c.low for c in candles[-14:-7]]
        recent_highs = [c.high for c in candles[-7:]]
        prior_highs = [c.high for c in candles[-14:-7]]

        # We only have the latest MACD histogram from indicators
        # For a simple implementation: check if price made new low but
        # current histogram is less negative than it was (approximation)
        current_hist = indicators.macd_histogram

        if min(recent_lows) < min(prior_lows) and current_hist > -abs(current_hist * 0.5):
            return "bullish"

        if max(recent_highs) > max(prior_highs) and current_hist < abs(current_hist * 0.5):
            return "bearish"

        return None

    @staticmethod
    def _compute_grade(strength: float) -> SignalGrade:
        """Assign grade based on composite strength."""
        if strength >= 0.80:
            return SignalGrade.A
        if strength >= 0.60:
            return SignalGrade.B
        if strength >= 0.40:
            return SignalGrade.C
        return SignalGrade.D

    @staticmethod
    def _calculate_stop_loss(
        candles: list,
        direction: Direction,
        atr: float,
        regime: MarketRegime = MarketRegime.RANGING,
    ) -> tuple[float, StopLossType]:
        """Calculate stop loss based on ATR with regime-specific multiplier.

        Enforces MIN_SL_PERCENT to prevent noise-triggered stops on short timeframes.
        """
        from app.config.constants import MIN_SL_PERCENT

        close = candles[-1].close

        regime_multipliers = {
            MarketRegime.TRENDING_UP: ATR_MULTIPLIER_TRENDING,
            MarketRegime.TRENDING_DOWN: ATR_MULTIPLIER_TRENDING,
            MarketRegime.RANGING: ATR_MULTIPLIER_RANGING,
            MarketRegime.HIGH_VOLATILITY: ATR_MULTIPLIER_VOLATILE,
            MarketRegime.LOW_VOLATILITY: ATR_MULTIPLIER_LOW_VOL,
        }
        multiplier = regime_multipliers.get(regime, ATR_MULTIPLIER_DEFAULT)

        sl_distance = atr * multiplier
        # Enforce minimum SL distance to prevent noise stops on short timeframes
        min_distance = close * MIN_SL_PERCENT
        if sl_distance < min_distance:
            sl_distance = min_distance

        if direction == Direction.LONG:
            sl = close - sl_distance
        else:
            sl = close + sl_distance

        return sl, StopLossType.ATR_BASED

    @staticmethod
    def _calculate_take_profits(
        entry: float,
        stop_loss: float,
        direction: Direction,
    ) -> list[TakeProfit]:
        """Calculate 3 take-profit levels based on R:R ratios."""
        risk = abs(entry - stop_loss)
        if risk == 0:
            risk = entry * 0.01

        tps = []
        for level, rr, pct in [
            ("TP1", TP1_RR_RATIO, TP1_CLOSE_PCT),
            ("TP2", TP2_RR_RATIO, TP2_CLOSE_PCT),
            ("TP3", TP3_RR_RATIO, TP3_CLOSE_PCT),
        ]:
            if direction == Direction.LONG:
                tp_price = entry + risk * rr
            else:
                tp_price = entry - risk * rr

            tps.append(TakeProfit(
                level=level,
                price=tp_price,
                close_pct=pct,
                rr_ratio=rr,
            ))

        return tps

    @staticmethod
    def _calculate_risk_reward(
        entry: float,
        stop_loss: float,
        take_profits: list[TakeProfit],
    ) -> RiskReward:
        """Calculate risk-reward ratios."""
        risk = abs(entry - stop_loss)
        if risk == 0:
            risk = entry * 0.01

        rr_values = {}
        for tp in take_profits:
            reward = abs(tp.price - entry)
            rr_values[tp.level] = reward / risk

        # Weighted R:R
        weighted = sum(
            rr_values.get(tp.level, 0) * tp.close_pct / 100
            for tp in take_profits
        )

        return RiskReward(
            rr_tp1=rr_values.get("TP1", 0),
            rr_tp2=rr_values.get("TP2", 0),
            rr_tp3=rr_values.get("TP3", 0),
            weighted_rr=weighted,
        )

    @staticmethod
    def _calculate_position_size(
        entry: float,
        stop_loss: float,
        portfolio_balance: float,
        risk_pct: float,
    ) -> PositionSize:
        """Calculate position size based on fixed-risk model.

        Caps leverage at MAX_LEVERAGE and adjusts quantity downward if needed.
        """
        from app.config.constants import MAX_LEVERAGE

        risk_amount = portfolio_balance * risk_pct
        risk_per_unit = abs(entry - stop_loss)

        if risk_per_unit == 0:
            risk_per_unit = entry * 0.01

        quantity = risk_amount / risk_per_unit
        notional = quantity * entry
        leverage = max(1, int(notional / portfolio_balance))

        # Cap leverage at max allowed — reduce position size if needed
        if leverage > MAX_LEVERAGE:
            leverage = MAX_LEVERAGE

        # Cap margin per trade at balance / max_positions to allow concurrent trades
        from app.config.constants import MAX_OPEN_POSITIONS
        max_margin_per_trade = portfolio_balance / MAX_OPEN_POSITIONS * 0.95
        max_notional = max_margin_per_trade * leverage
        if notional > max_notional:
            quantity = max_notional / entry
            notional = quantity * entry
            risk_amount = quantity * risk_per_unit

        margin = notional / leverage

        return PositionSize(
            quantity=quantity,
            notional=notional,
            margin=margin,
            risk_amount=risk_amount,
            risk_pct=risk_pct,
            leverage=leverage,
        )
