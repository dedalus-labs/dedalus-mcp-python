# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Tests for DPoP (Demonstrating Proof of Possession) validation.

Implements test cases per RFC 9449 to ensure server-side proof validation
correctly enforces sender constraints on access tokens.
"""

from __future__ import annotations

import base64
import hashlib
import json
import time
import uuid
from typing import Any

import pytest

from dedalus_mcp.server.services.dpop import (
    DPoPValidator,
    DPoPValidatorConfig,
    DPoPValidationError,
    InvalidDPoPProofError,
    DPoPReplayError,
    DPoPMethodMismatchError,
    DPoPUrlMismatchError,
    DPoPExpiredError,
    DPoPThumbprintMismatchError,
)


def _b64url_encode(data: bytes) -> str:
    """Base64url encode without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
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


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(now=1700000000.0)


@pytest.fixture
def es256_keypair():
    """Generate an ES256 key pair for testing."""
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.backends import default_backend

    private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
    return private_key


def _build_dpop_proof(
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
) -> str:
    """Build a DPoP proof JWT for testing."""
    import jwt
    from cryptography.hazmat.primitives import serialization

    # Extract public key as JWK
    public_key = private_key.public_key()
    public_numbers = public_key.public_numbers()

    # Compute x and y coordinates as base64url
    x_bytes = public_numbers.x.to_bytes(32, byteorder="big")
    y_bytes = public_numbers.y.to_bytes(32, byteorder="big")

    jwk = {"kty": "EC", "crv": "P-256", "x": _b64url_encode(x_bytes), "y": _b64url_encode(y_bytes)}

    header = {"typ": typ, "alg": alg, "jwk": jwk}
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

    # Sign with private key
    return jwt.encode(payload, private_key, algorithm="ES256", headers=header)


def _compute_jwk_thumbprint(jwk: dict[str, Any]) -> str:
    """Compute JWK thumbprint per RFC 7638."""
    # For EC keys, required members are: crv, kty, x, y (alphabetical order)
    canonical = json.dumps(
        {"crv": jwk["crv"], "kty": jwk["kty"], "x": jwk["x"], "y": jwk["y"]}, separators=(",", ":"), sort_keys=True
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).digest()
    return _b64url_encode(digest)


def _compute_ath(access_token: str) -> str:
    """Compute access token hash for ath claim."""
    digest = hashlib.sha256(access_token.encode("ascii")).digest()
    return _b64url_encode(digest)


# =============================================================================
# Test cases - these define our invariants
# =============================================================================


class TestDPoPProofParsing:
    """Tests for basic DPoP proof structure validation."""

    def test_valid_proof_parses_successfully(self, es256_keypair, clock):
        """A well-formed DPoP proof with valid signature should parse."""
        proof = _build_dpop_proof(es256_keypair, htm="POST", htu="https://mcp.example.com/messages", iat=clock.now())

        config = DPoPValidatorConfig(clock=clock)
        validator = DPoPValidator(config)

        result = validator.validate_proof(proof=proof, method="POST", url="https://mcp.example.com/messages")

        assert result.jti is not None
        assert result.htm == "POST"
        assert result.htu == "https://mcp.example.com/messages"

    def test_missing_typ_header_rejected(self, es256_keypair, clock):
        """Proof without typ=dpop+jwt header should be rejected."""
        proof = _build_dpop_proof(es256_keypair, iat=clock.now(), typ="jwt")

        config = DPoPValidatorConfig(clock=clock)
        validator = DPoPValidator(config)

        with pytest.raises(InvalidDPoPProofError, match="typ"):
            validator.validate_proof(proof=proof, method="POST", url="https://mcp.example.com/messages")

    def test_missing_jwk_header_rejected(self, es256_keypair, clock):
        """Proof without embedded JWK should be rejected."""
        import jwt as pyjwt

        # Build proof manually without JWK in header
        header = {"typ": "dpop+jwt", "alg": "ES256"}
        payload = {
            "jti": str(uuid.uuid4()),
            "htm": "POST",
            "htu": "https://mcp.example.com/messages",
            "iat": int(clock.now()),
        }
        proof = pyjwt.encode(payload, es256_keypair, algorithm="ES256", headers=header)

        config = DPoPValidatorConfig(clock=clock)
        validator = DPoPValidator(config)

        with pytest.raises(InvalidDPoPProofError, match="jwk"):
            validator.validate_proof(proof=proof, method="POST", url="https://mcp.example.com/messages")

    def test_missing_required_claim_rejected(self, es256_keypair, clock):
        """Proof missing jti/htm/htu/iat should be rejected."""
        import jwt as pyjwt

        # Build proof without jti
        public_key = es256_keypair.public_key()
        public_numbers = public_key.public_numbers()
        x_bytes = public_numbers.x.to_bytes(32, byteorder="big")
        y_bytes = public_numbers.y.to_bytes(32, byteorder="big")
        jwk = {"kty": "EC", "crv": "P-256", "x": _b64url_encode(x_bytes), "y": _b64url_encode(y_bytes)}

        header = {"typ": "dpop+jwt", "alg": "ES256", "jwk": jwk}
        payload = {
            # Missing jti
            "htm": "POST",
            "htu": "https://mcp.example.com/messages",
            "iat": int(clock.now()),
        }
        proof = pyjwt.encode(payload, es256_keypair, algorithm="ES256", headers=header)

        config = DPoPValidatorConfig(clock=clock)
        validator = DPoPValidator(config)

        with pytest.raises(InvalidDPoPProofError, match="jti"):
            validator.validate_proof(proof=proof, method="POST", url="https://mcp.example.com/messages")


class TestDPoPMethodUrlBinding:
    """Tests for HTTP method and URL binding validation."""

    def test_method_mismatch_rejected(self, es256_keypair, clock):
        """Proof bound to POST should not validate for GET request."""
        proof = _build_dpop_proof(es256_keypair, htm="POST", iat=clock.now())

        config = DPoPValidatorConfig(clock=clock)
        validator = DPoPValidator(config)

        with pytest.raises(DPoPMethodMismatchError):
            validator.validate_proof(
                proof=proof,
                method="GET",  # Mismatch
                url="https://mcp.example.com/messages",
            )

    def test_url_mismatch_rejected(self, es256_keypair, clock):
        """Proof bound to one URL should not validate for different URL."""
        proof = _build_dpop_proof(es256_keypair, htu="https://mcp.example.com/messages", iat=clock.now())

        config = DPoPValidatorConfig(clock=clock)
        validator = DPoPValidator(config)

        with pytest.raises(DPoPUrlMismatchError):
            validator.validate_proof(
                proof=proof,
                method="POST",
                url="https://different.example.com/messages",  # Mismatch
            )

    def test_url_normalization(self, es256_keypair, clock):
        """URL comparison should be case-insensitive for scheme/host."""
        proof = _build_dpop_proof(es256_keypair, htu="https://MCP.Example.COM/messages", iat=clock.now())

        config = DPoPValidatorConfig(clock=clock)
        validator = DPoPValidator(config)

        # Should match despite different casing
        result = validator.validate_proof(proof=proof, method="POST", url="https://mcp.example.com/messages")
        assert result is not None

    def test_url_strips_query_and_fragment(self, es256_keypair, clock):
        """Per RFC 9449 Section 4.2, htu should match without query/fragment."""
        # Proof has htu without query/fragment (as per spec)
        proof = _build_dpop_proof(es256_keypair, htu="https://mcp.example.com/messages", iat=clock.now())

        config = DPoPValidatorConfig(clock=clock)
        validator = DPoPValidator(config)

        # Request URL has query and fragment - should still match
        result = validator.validate_proof(
            proof=proof, method="POST", url="https://mcp.example.com/messages?foo=bar#section"
        )
        assert result is not None


class TestDPoPJWKValidation:
    """Tests for JWK validation per RFC 9449 Section 4.3."""

    def test_jwk_with_private_key_rejected(self, es256_keypair, clock):
        """Per RFC 9449 Section 4.3 point 7, jwk must not contain private key."""
        import jwt as pyjwt

        public_key = es256_keypair.public_key()
        public_numbers = public_key.public_numbers()
        x_bytes = public_numbers.x.to_bytes(32, byteorder="big")
        y_bytes = public_numbers.y.to_bytes(32, byteorder="big")

        # Get private key bytes
        private_numbers = es256_keypair.private_numbers()
        d_bytes = private_numbers.private_value.to_bytes(32, byteorder="big")

        # Include private key material (d) in the JWK - this is invalid
        jwk_with_private = {
            "kty": "EC",
            "crv": "P-256",
            "x": _b64url_encode(x_bytes),
            "y": _b64url_encode(y_bytes),
            "d": _b64url_encode(d_bytes),  # Private key material - FORBIDDEN
        }

        header = {"typ": "dpop+jwt", "alg": "ES256", "jwk": jwk_with_private}
        payload = {
            "jti": str(uuid.uuid4()),
            "htm": "POST",
            "htu": "https://mcp.example.com/messages",
            "iat": int(clock.now()),
        }
        proof = pyjwt.encode(payload, es256_keypair, algorithm="ES256", headers=header)

        config = DPoPValidatorConfig(clock=clock)
        validator = DPoPValidator(config)

        with pytest.raises(InvalidDPoPProofError, match="private key"):
            validator.validate_proof(proof=proof, method="POST", url="https://mcp.example.com/messages")


class TestDPoPTimeValidation:
    """Tests for iat claim time validation."""

    def test_expired_proof_rejected(self, es256_keypair, clock):
        """Proof with iat too far in the past should be rejected."""
        # Create proof 5 minutes ago
        proof = _build_dpop_proof(es256_keypair, iat=clock.now() - 300)

        config = DPoPValidatorConfig(clock=clock, leeway=60)  # 60s leeway
        validator = DPoPValidator(config)

        with pytest.raises(DPoPExpiredError):
            validator.validate_proof(proof=proof, method="POST", url="https://mcp.example.com/messages")

    def test_future_proof_rejected(self, es256_keypair, clock):
        """Proof with iat too far in the future should be rejected."""
        # Create proof 5 minutes in the future
        proof = _build_dpop_proof(es256_keypair, iat=clock.now() + 300)

        config = DPoPValidatorConfig(clock=clock, leeway=60)
        validator = DPoPValidator(config)

        with pytest.raises(DPoPExpiredError):
            validator.validate_proof(proof=proof, method="POST", url="https://mcp.example.com/messages")

    def test_within_leeway_accepted(self, es256_keypair, clock):
        """Proof within leeway window should be accepted."""
        # Create proof 30s ago (within 60s leeway)
        proof = _build_dpop_proof(es256_keypair, iat=clock.now() - 30)

        config = DPoPValidatorConfig(clock=clock, leeway=60)
        validator = DPoPValidator(config)

        result = validator.validate_proof(proof=proof, method="POST", url="https://mcp.example.com/messages")
        assert result is not None


class TestDPoPReplayProtection:
    """Tests for JTI replay attack prevention."""

    def test_replay_detected(self, es256_keypair, clock):
        """Same JTI used twice should be rejected."""
        jti = str(uuid.uuid4())
        proof = _build_dpop_proof(es256_keypair, jti=jti, iat=clock.now())

        config = DPoPValidatorConfig(clock=clock)
        validator = DPoPValidator(config)

        # First use succeeds
        validator.validate_proof(proof=proof, method="POST", url="https://mcp.example.com/messages")

        # Replay attempt fails
        with pytest.raises(DPoPReplayError):
            validator.validate_proof(proof=proof, method="POST", url="https://mcp.example.com/messages")

    def test_different_jti_succeeds(self, es256_keypair, clock):
        """Different JTIs should both succeed."""
        config = DPoPValidatorConfig(clock=clock)
        validator = DPoPValidator(config)

        proof1 = _build_dpop_proof(es256_keypair, jti=str(uuid.uuid4()), iat=clock.now())
        proof2 = _build_dpop_proof(es256_keypair, jti=str(uuid.uuid4()), iat=clock.now())

        result1 = validator.validate_proof(proof=proof1, method="POST", url="https://mcp.example.com/messages")
        result2 = validator.validate_proof(proof=proof2, method="POST", url="https://mcp.example.com/messages")

        assert result1.jti != result2.jti

    def test_jti_cache_eviction(self, es256_keypair, clock):
        """Old JTIs should be evicted after TTL expires."""
        jti = str(uuid.uuid4())
        proof = _build_dpop_proof(es256_keypair, jti=jti, iat=clock.now())

        config = DPoPValidatorConfig(clock=clock, jti_cache_ttl=60)
        validator = DPoPValidator(config)

        # First use succeeds
        validator.validate_proof(proof=proof, method="POST", url="https://mcp.example.com/messages")

        # Advance time past TTL
        clock.advance(120)

        # Create new proof with fresh iat but same jti
        # (In practice you'd use a new jti, but this tests eviction)
        proof2 = _build_dpop_proof(es256_keypair, jti=jti, iat=clock.now())
        result = validator.validate_proof(proof=proof2, method="POST", url="https://mcp.example.com/messages")
        assert result is not None


class TestDPoPThumbprintBinding:
    """Tests for access token binding via cnf.jkt claim."""

    def test_thumbprint_match_succeeds(self, es256_keypair, clock):
        """Proof key matching token's cnf.jkt should succeed."""
        proof = _build_dpop_proof(es256_keypair, iat=clock.now())

        # Extract JWK from proof header to compute expected thumbprint
        import jwt

        header = jwt.get_unverified_header(proof)
        expected_thumbprint = _compute_jwk_thumbprint(header["jwk"])

        config = DPoPValidatorConfig(clock=clock)
        validator = DPoPValidator(config)

        result = validator.validate_proof(
            proof=proof, method="POST", url="https://mcp.example.com/messages", expected_thumbprint=expected_thumbprint
        )
        assert result is not None

    def test_thumbprint_mismatch_rejected(self, es256_keypair, clock):
        """Proof key not matching token's cnf.jkt should be rejected."""
        proof = _build_dpop_proof(es256_keypair, iat=clock.now())

        config = DPoPValidatorConfig(clock=clock)
        validator = DPoPValidator(config)

        with pytest.raises(DPoPThumbprintMismatchError):
            validator.validate_proof(
                proof=proof,
                method="POST",
                url="https://mcp.example.com/messages",
                expected_thumbprint="wrongthumbprint123",  # Deliberate mismatch
            )


class TestDPoPAccessTokenHash:
    """Tests for ath (access token hash) claim validation."""

    def test_ath_validated_when_present(self, es256_keypair, clock):
        """When ath claim present, it should match hash of access token."""
        access_token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.test"
        expected_ath = _compute_ath(access_token)

        proof = _build_dpop_proof(es256_keypair, iat=clock.now(), ath=expected_ath)

        config = DPoPValidatorConfig(clock=clock)
        validator = DPoPValidator(config)

        result = validator.validate_proof(
            proof=proof, method="POST", url="https://mcp.example.com/messages", access_token=access_token
        )
        assert result is not None

    def test_ath_mismatch_rejected(self, es256_keypair, clock):
        """When ath present but doesn't match access token hash, reject."""
        proof = _build_dpop_proof(es256_keypair, iat=clock.now(), ath="wronghash123")

        config = DPoPValidatorConfig(clock=clock)
        validator = DPoPValidator(config)

        with pytest.raises(InvalidDPoPProofError, match="ath"):
            validator.validate_proof(
                proof=proof,
                method="POST",
                url="https://mcp.example.com/messages",
                access_token="eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.test",
            )


class TestJWKThumbprint:
    """Tests for RFC 7638 JWK thumbprint computation."""

    def test_ec_key_thumbprint_computation(self, es256_keypair):
        """EC key thumbprint should follow RFC 7638 canonicalization."""
        public_key = es256_keypair.public_key()
        public_numbers = public_key.public_numbers()

        x_bytes = public_numbers.x.to_bytes(32, byteorder="big")
        y_bytes = public_numbers.y.to_bytes(32, byteorder="big")

        jwk = {"kty": "EC", "crv": "P-256", "x": _b64url_encode(x_bytes), "y": _b64url_encode(y_bytes)}

        thumbprint = _compute_jwk_thumbprint(jwk)

        # Verify it's base64url encoded SHA-256 (43 chars without padding)
        assert len(thumbprint) == 43
        assert "=" not in thumbprint

        # Verify canonicalization order: crv, kty, x, y
        canonical = json.dumps(
            {"crv": jwk["crv"], "kty": jwk["kty"], "x": jwk["x"], "y": jwk["y"]}, separators=(",", ":"), sort_keys=True
        )
        expected = _b64url_encode(hashlib.sha256(canonical.encode()).digest())
        assert thumbprint == expected
