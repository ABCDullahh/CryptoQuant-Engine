"""Settings endpoints — exchange keys, risk params, notifications."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_current_user, get_db
from app.api.schemas import (
    DCASettingsUpdate,
    ExchangeSettingsUpdate,
    NotificationSettingsUpdate,
    RiskSettingsUpdate,
)
from app.config.constants import (
    DEFAULT_LEVERAGE,
    MAX_DAILY_LOSS,
    MAX_DRAWDOWN,
    MAX_LEVERAGE,
    MAX_OPEN_POSITIONS,
    MAX_PORTFOLIO_HEAT,
    MAX_RISK_PER_TRADE,
)
from app.config.settings import get_settings

router = APIRouter()


def _get_fernet() -> Fernet:
    """Derive a Fernet key from the JWT secret for encrypting exchange keys."""
    secret = get_settings().jwt_secret.encode("utf-8")
    key = base64.urlsafe_b64encode(hashlib.sha256(secret).digest())
    return Fernet(key)


def encrypt_exchange_keys(api_key: str, api_secret: str, testnet: bool) -> bytes:
    """Encrypt exchange keys using Fernet (AES-128-CBC)."""
    plaintext = f"{api_key}:{api_secret}:{testnet}"
    return _get_fernet().encrypt(plaintext.encode("utf-8"))


def decrypt_exchange_keys(encrypted: bytes) -> tuple[str, str, bool]:
    """Decrypt exchange keys. Returns (api_key, api_secret, testnet)."""
    try:
        plaintext = _get_fernet().decrypt(encrypted).decode("utf-8")
        parts = plaintext.split(":", 2)
        return parts[0], parts[1], parts[2].lower() == "true"
    except (InvalidToken, IndexError, ValueError) as exc:
        raise ValueError("Failed to decrypt exchange keys") from exc


async def _get_user_settings(db):
    """Get or create user settings record."""
    from sqlalchemy import select
    from app.db.models import UserSettingsModel

    result = await db.execute(select(UserSettingsModel).limit(1))
    settings = result.scalar_one_or_none()
    if settings is None:
        settings = UserSettingsModel(
            risk_params={
                "default_risk_pct": MAX_RISK_PER_TRADE,
                "max_leverage": MAX_LEVERAGE,
                "default_leverage": DEFAULT_LEVERAGE,
                "max_positions": MAX_OPEN_POSITIONS,
                "max_portfolio_heat": MAX_PORTFOLIO_HEAT,
                "max_daily_loss": MAX_DAILY_LOSS,
                "max_drawdown": MAX_DRAWDOWN,
            },
            strategy_config={},
            notification_config={
                "telegram_enabled": False,
                "discord_enabled": False,
            },
        )
        db.add(settings)
        await db.flush()
    return settings


@router.get("")
async def get_user_settings(
    db=Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Get all current settings."""
    settings = await _get_user_settings(db)
    app_settings = get_settings()

    # Check if keys are configured via DB (user-saved) or via .env
    db_configured = settings.exchange_keys_encrypted is not None
    env_configured = bool(app_settings.binance_api_key)
    configured = db_configured or env_configured

    # Mask key for display
    if db_configured:
        api_key_masked = "***"
    elif env_configured:
        key = app_settings.binance_api_key
        api_key_masked = f"{key[:4]}...{key[-4:]}"
    else:
        api_key_masked = None

    return {
        "exchange": {
            "api_key_masked": api_key_masked,
            "configured": configured,
            "source": "database" if db_configured else ("env" if env_configured else None),
            "testnet": app_settings.binance_testnet if env_configured else None,
        },
        "risk_params": settings.risk_params or {},
        "strategy_config": settings.strategy_config or {},
        "notification_config": settings.notification_config or {},
        "signal_policy": settings.signal_policy or {},
    }


@router.put("/exchange")
async def update_exchange_keys(
    request: ExchangeSettingsUpdate,
    db=Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Update exchange API keys (stored encrypted)."""
    settings = await _get_user_settings(db)

    settings.exchange_keys_encrypted = encrypt_exchange_keys(
        request.api_key, request.api_secret, request.testnet
    )
    await db.commit()

    return {"status": "updated", "testnet": request.testnet}


@router.put("/risk")
async def update_risk_params(
    request: RiskSettingsUpdate,
    db=Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Update risk parameters."""
    settings = await _get_user_settings(db)
    current = settings.risk_params or {}

    # Update only provided fields — create new dict for SQLAlchemy change detection
    update = request.model_dump(exclude_none=True)
    settings.risk_params = {**current, **update}
    await db.commit()

    return {"risk_params": settings.risk_params}


@router.get("/dca")
async def get_dca_settings(
    db=Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Get DCA configuration."""
    settings = await _get_user_settings(db)
    risk = settings.risk_params or {}
    dca_config = risk.get("dca_config", {
        "enabled": False,
        "max_dca_orders": 3,
        "trigger_drop_pct": [2.0, 4.0, 6.0],
        "qty_multiplier": [1.0, 1.5, 2.0],
        "max_total_risk_pct": 5.0,
        "sl_recalc_mode": "follow",
        "tp_recalc_mode": "recalculate",
    })
    return {"dca_config": dca_config}


@router.put("/dca")
async def update_dca_settings(
    request: DCASettingsUpdate,
    db=Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Update DCA configuration."""
    settings = await _get_user_settings(db)
    risk = settings.risk_params or {}
    current_dca = risk.get("dca_config", {})

    update = request.model_dump(exclude_none=True)

    # Validate trigger_drop_pct and qty_multiplier have matching lengths
    new_dca = {**current_dca, **update}
    triggers = new_dca.get("trigger_drop_pct", [])
    multipliers = new_dca.get("qty_multiplier", [])
    max_orders = new_dca.get("max_dca_orders", 3)

    if triggers and len(triggers) != max_orders:
        raise HTTPException(400, "trigger_drop_pct length must match max_dca_orders")
    if multipliers and len(multipliers) != max_orders:
        raise HTTPException(400, "qty_multiplier length must match max_dca_orders")

    # Validate ranges
    if "max_dca_orders" in update and not (1 <= update["max_dca_orders"] <= 5):
        raise HTTPException(400, "max_dca_orders must be 1-5")
    if "max_total_risk_pct" in update and not (0.5 <= update["max_total_risk_pct"] <= 20.0):
        raise HTTPException(400, "max_total_risk_pct must be 0.5-20%")

    risk["dca_config"] = new_dca
    settings.risk_params = {**risk}  # New dict for SQLAlchemy change detection
    await db.commit()

    return {"dca_config": new_dca}


@router.put("/notifications")
async def update_notifications(
    request: NotificationSettingsUpdate,
    db=Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Update notification preferences."""
    settings = await _get_user_settings(db)
    current = settings.notification_config or {}

    # Create new dict for SQLAlchemy change detection
    update = request.model_dump(exclude_none=True)
    settings.notification_config = {**current, **update}
    await db.commit()

    return {"notification_config": settings.notification_config}


# ---------------------------------------------------------------------------
# Signal Execution Policy
# ---------------------------------------------------------------------------

@router.get("/signal-policy")
async def get_signal_policy(
    db=Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Get signal execution policy (per-strategy × per-grade matrix)."""
    from app.config.constants import SIGNAL_POLICY_PRESETS

    settings = await _get_user_settings(db)
    policy = settings.signal_policy or {}

    # Default to balanced preset if not set
    if not policy.get("matrix"):
        policy = {
            "preset": "balanced",
            "matrix": SIGNAL_POLICY_PRESETS["balanced"],
            "max_auto_per_hour": 5,
            "quiet_hours_start": None,
            "quiet_hours_end": None,
        }

    return {"signal_policy": policy}


@router.put("/signal-policy")
async def update_signal_policy(
    request: dict,
    db=Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Update signal execution policy."""
    settings = await _get_user_settings(db)

    # Validate actions in matrix
    valid_actions = {"auto", "alert", "queue", "skip"}
    matrix = request.get("matrix", {})
    for strategy_name, grades in matrix.items():
        for grade, action in grades.items():
            if action not in valid_actions:
                from fastapi import HTTPException
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid action '{action}' for {strategy_name}/{grade}. Must be: {valid_actions}",
                )

    settings.signal_policy = {**request}
    await db.commit()

    return {"signal_policy": settings.signal_policy}


@router.post("/signal-policy/preset")
async def apply_signal_policy_preset(
    request: dict,
    db=Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Apply a preset signal policy (conservative/balanced/aggressive)."""
    from app.config.constants import SIGNAL_POLICY_PRESETS

    preset_name = request.get("preset", "balanced")
    if preset_name not in SIGNAL_POLICY_PRESETS:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=400,
            detail=f"Invalid preset '{preset_name}'. Must be: {list(SIGNAL_POLICY_PRESETS.keys())}",
        )

    settings = await _get_user_settings(db)
    current = settings.signal_policy or {}

    settings.signal_policy = {
        **current,
        "preset": preset_name,
        "matrix": SIGNAL_POLICY_PRESETS[preset_name],
    }
    await db.commit()

    return {"signal_policy": settings.signal_policy}
