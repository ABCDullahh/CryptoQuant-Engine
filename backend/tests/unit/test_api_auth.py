"""Tests for API auth module — JWT creation, validation, password hashing."""

from __future__ import annotations

import time

import pytest

from app.api.auth import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


class TestJWT:
    def test_create_and_decode_token(self):
        """Create a token and decode it back."""
        token = create_access_token("testuser")
        subject = decode_access_token(token)
        assert subject == "testuser"

    def test_decode_invalid_token(self):
        """Invalid token returns None."""
        result = decode_access_token("invalid.token.here")
        assert result is None

    def test_decode_empty_token(self):
        """Empty token returns None."""
        result = decode_access_token("")
        assert result is None

    def test_different_subjects(self):
        """Different subjects produce different tokens."""
        t1 = create_access_token("user1")
        t2 = create_access_token("user2")
        assert t1 != t2
        assert decode_access_token(t1) == "user1"
        assert decode_access_token(t2) == "user2"

    def test_token_is_string(self):
        """Token is a string."""
        token = create_access_token("admin")
        assert isinstance(token, str)
        assert len(token) > 20


class TestPasswordHashing:
    def test_hash_and_verify(self):
        """Hash a password and verify it."""
        hashed = hash_password("mysecretpassword")
        assert verify_password("mysecretpassword", hashed)

    def test_wrong_password(self):
        """Wrong password fails verification."""
        hashed = hash_password("correct")
        assert not verify_password("wrong", hashed)

    def test_hash_is_different_each_time(self):
        """Hashing the same password produces different hashes (salt)."""
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2  # Different salts
        assert verify_password("same", h1)
        assert verify_password("same", h2)

    def test_hash_is_string(self):
        """Hash result is a string."""
        hashed = hash_password("test")
        assert isinstance(hashed, str)
        assert "$2" in hashed  # bcrypt prefix ($2b$ or $2a$)
