"""Wallet endpoints — balances across wallet types, internal transfers."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_current_user
from app.api.schemas import TransferRequest
from app.data.providers.exchange_factory import create_exchange

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/balances")
async def get_wallet_balances(user: str = Depends(get_current_user)):
    """Fetch balances from multiple Binance wallet types (spot, future, funding)."""
    exchange = await create_exchange(auth=True)
    try:
        await exchange.load_markets()
        all_assets: dict[str, dict] = {}
        account_types = {
            "spot": {"type": "spot"},
            "future": {},  # default for binanceusdm
            "funding": {"type": "funding"},
        }

        for wallet_name, params in account_types.items():
            try:
                balance = await exchange.fetch_balance(params=params)
                for currency, data in balance.items():
                    if not isinstance(data, dict) or "total" not in data:
                        continue
                    total = float(data.get("total", 0) or 0)
                    if total == 0:
                        continue
                    if currency not in all_assets:
                        all_assets[currency] = {
                            "currency": currency,
                            "total": 0,
                            "free": 0,
                            "used": 0,
                            "wallets": {},
                        }
                    all_assets[currency]["total"] += total
                    all_assets[currency]["free"] += float(data.get("free", 0) or 0)
                    all_assets[currency]["used"] += float(data.get("used", 0) or 0)
                    all_assets[currency]["wallets"][wallet_name] = {
                        "total": total,
                        "free": float(data.get("free", 0) or 0),
                        "used": float(data.get("used", 0) or 0),
                    }
            except Exception as exc:
                logger.warning(
                    "wallet.balance_fetch_failed",
                    wallet=wallet_name,
                    error=str(exc),
                )

        assets = sorted(all_assets.values(), key=lambda a: -a["total"])
        total_usd = sum(
            a["total"]
            for a in assets
            if a["currency"] in ("USDT", "USDC", "BUSD", "FDUSD")
        )

        return {
            "assets": assets,
            "total_usd_value": total_usd,
            "wallet_count": len(account_types),
        }
    finally:
        await exchange.close()


@router.post("/transfer")
async def transfer_funds(
    request: TransferRequest,
    user: str = Depends(get_current_user),
):
    """Internal wallet transfer using CCXT unified transfer()."""
    from_wallet = request.from_wallet
    to_wallet = request.to_wallet
    currency = request.currency
    amount = request.amount

    # Validation (Pydantic handles type/range; these are business rules)
    valid_wallets = ["spot", "future", "margin", "funding"]
    if from_wallet not in valid_wallets or to_wallet not in valid_wallets:
        raise HTTPException(status_code=400, detail="Invalid wallet type")
    if from_wallet == to_wallet:
        raise HTTPException(
            status_code=400, detail="From and To wallet must be different"
        )

    # Demo/testnet accounts don't support sapi endpoints (wallet transfers)
    from app.config.settings import get_settings
    settings = get_settings()
    if settings.binance_testnet:
        raise HTTPException(
            status_code=400,
            detail="Wallet transfers are not supported on Binance Demo accounts. "
                   "This feature requires a live Binance account with sapi access."
        )

    exchange = await create_exchange(auth=True)
    try:
        await exchange.load_markets()
        result = await exchange.transfer(currency, amount, from_wallet, to_wallet)
        return {
            "id": result.get("id", ""),
            "from_wallet": from_wallet,
            "to_wallet": to_wallet,
            "currency": currency,
            "amount": amount,
            "status": result.get("status", "ok"),
            "timestamp": result.get("datetime", ""),
        }
    except Exception as exc:
        logger.error("wallet.transfer_failed", error=str(exc))
        raise HTTPException(
            status_code=400, detail=f"Transfer failed: {str(exc)}"
        )
    finally:
        await exchange.close()


@router.get("/transfers")
async def get_transfer_history(
    limit: int = 50,
    user: str = Depends(get_current_user),
):
    """Fetch transfer history."""
    exchange = await create_exchange(auth=True)
    try:
        await exchange.load_markets()
        try:
            transfers = await exchange.fetch_transfers(code=None, limit=limit)
            return {
                "transfers": [
                    {
                        "id": t.get("id", ""),
                        "from": t.get("fromAccount", ""),
                        "to": t.get("toAccount", ""),
                        "currency": t.get("currency", ""),
                        "amount": float(t.get("amount", 0)),
                        "status": t.get("status", ""),
                        "timestamp": t.get("datetime", ""),
                    }
                    for t in (transfers or [])
                ],
                "count": len(transfers or []),
            }
        except Exception as exc:
            logger.warning(
                "wallet.fetch_transfers_not_supported", error=str(exc)
            )
            return {
                "transfers": [],
                "count": 0,
                "note": "Transfer history not available on this account type",
            }
    finally:
        await exchange.close()
