"""Authentication endpoints — register and login."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from pydantic import BaseModel

from app.api.auth import create_access_token, hash_password, verify_password
from app.api.dependencies import get_current_user, get_db
from app.api.schemas import TokenRequest, TokenResponse
from app.db.models import UserModel

router = APIRouter()


class RegisterRequest(TokenRequest):
    """Registration uses the same fields as login."""
    pass


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(request: RegisterRequest, db=Depends(get_db)):
    """Register a new user account."""
    # Check if username already exists
    result = await db.execute(
        select(UserModel).where(UserModel.username == request.username)
    )
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        )

    user = UserModel(
        username=request.username,
        hashed_password=hash_password(request.password),
    )
    db.add(user)
    await db.commit()

    token = create_access_token(subject=user.username)
    return TokenResponse(access_token=token, expires_in=86400)


@router.post("/login", response_model=TokenResponse)
async def login(request: TokenRequest, db=Depends(get_db)):
    """Login and obtain a JWT access token."""
    result = await db.execute(
        select(UserModel).where(UserModel.username == request.username)
    )
    user = result.scalar_one_or_none()

    if user is None or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(subject=user.username)
    return TokenResponse(access_token=token, expires_in=86400)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.put("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    db=Depends(get_db),
    username: str = Depends(get_current_user),
):
    """Change the current user's password."""
    result = await db.execute(
        select(UserModel).where(UserModel.username == username)
    )
    user_row = result.scalar_one_or_none()

    if user_row is None or not verify_password(
        request.current_password, user_row.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )

    if len(request.new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 6 characters",
        )

    user_row.hashed_password = hash_password(request.new_password)
    await db.commit()

    return {"status": "password_updated"}
