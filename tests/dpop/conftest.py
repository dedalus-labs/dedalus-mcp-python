# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Shared fixtures for DPoP tests."""

from __future__ import annotations

import base64
import hashlib
import json
import time
from typing import Any
import uuid

import pytest


def b64url_encode(data: bytes) -> str:
    """Base64url encode without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(s: str) -> bytes:
    """Base64url decode with padding restoration."""
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


class FakeClock:
    """Controllable clock for testing time-dependent logic."""

    def __init__(self, now: float | None = None) -> None:
        self._now = now if now is not None else time.time()

    def now(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += seconds

    def set(self, timestamp: float) -> None:
        self._now = timestamp


@pytest.fixture
def clock() -> FakeClock:
    """Controllable clock starting at a fixed timestamp."""
    return FakeClock(now=1700000000.0)


@pytest.fixture
def es256_keypair():
    """Generate an ES256 (P-256) key pair for testing."""
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.asymmetric import ec

    private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
    return private_key


@pytest.fixture
def es256_keypair_alt():
    """Generate a second ES256 key pair (for testing key mismatch)."""
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.asymmetric import ec

    private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
    return private_key


def build_dpop_proof(
    private_key,
    *,
    htm: str = "POST",
    htu: str = "https://mcp.example.com/messages",
    jti: str | None = None,
    iat: float | None = None,
    ath: str | None = None,
    nonce: str | None = None,
    extra_claims: dict[str, Any] | None = None,
    extra_header: dict[str, Any] | None = None,
    typ: str = "dpop+jwt",
    alg: str = "ES256",
    include_jwk: bool = True,
    jwk_override: dict[str, Any] | None = None,
) -> str:
    """Build a DPoP proof JWT for testing.

    This helper allows creating both valid and intentionally invalid proofs
    for comprehensive test coverage.
    """
    import jwt

    # Extract public key as JWK
    public_key = private_key.public_key()
    public_numbers = public_key.public_numbers()

    x_bytes = public_numbers.x.to_bytes(32, byteorder="big")
    y_bytes = public_numbers.y.to_bytes(32, byteorder="big")

    jwk = {"kty": "EC", "crv": "P-256", "x": b64url_encode(x_bytes), "y": b64url_encode(y_bytes)}

    if jwk_override:
        jwk.update(jwk_override)

    header: dict[str, Any] = {"typ": typ, "alg": alg}
    if include_jwk:
        header["jwk"] = jwk
    if extra_header:
        header.update(extra_header)

    payload: dict[str, Any] = {
        "jti": jti or str(uuid.uuid4()),
        "htm": htm,
        "htu": htu,
        "iat": int(iat if iat is not None else time.time()),
    }
    if ath is not None:
        payload["ath"] = ath
    if nonce is not None:
        payload["nonce"] = nonce
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, private_key, algorithm="ES256", headers=header)


def compute_jwk_thumbprint(jwk: dict[str, Any]) -> str:
    """Compute JWK thumbprint per RFC 7638."""
    canonical = json.dumps(
        {"crv": jwk["crv"], "kty": jwk["kty"], "x": jwk["x"], "y": jwk["y"]}, separators=(",", ":"), sort_keys=True
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).digest()
    return b64url_encode(digest)


def compute_ath(access_token: str) -> str:
    """Compute access token hash for ath claim."""
    digest = hashlib.sha256(access_token.encode("ascii")).digest()
    return b64url_encode(digest)


def get_thumbprint_from_proof(proof: str) -> str:
    """Extract JWK from proof header and compute its thumbprint."""
    import jwt

    header = jwt.get_unverified_header(proof)
    return compute_jwk_thumbprint(header["jwk"])
