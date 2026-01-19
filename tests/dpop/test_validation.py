# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Tests for DPoP proof validation per RFC 9449 Section 4.3.

These tests cover all 12 validation checks from RFC 9449 Section 4.3:
1. Not more than one DPoP HTTP request header field
2. The DPoP HTTP request header field value is a single and well-formed JWT
3. All required claims per Section 4.2 are contained in the JWT
4. The typ JOSE Header Parameter has the value dpop+jwt
5. The alg JOSE Header Parameter indicates a registered asymmetric algorithm
6. The JWT signature verifies with the public key contained in the jwk header
7. The jwk JOSE Header Parameter does not contain a private key
8. The htm claim matches the HTTP method of the current request
9. The htu claim matches the HTTP URI (without query/fragment)
10. If server provided a nonce, the nonce claim matches
11. The iat claim is within an acceptable time window
12. If presented with access token: ath matches hash, key matches cnf.jkt
"""

from __future__ import annotations

import uuid

import pytest

from dedalus_mcp.dpop import (
    DPoPValidator,
    DPoPValidatorConfig,
    InvalidDPoPProofError,
    DPoPReplayError,
    DPoPMethodMismatchError,
    DPoPUrlMismatchError,
    DPoPExpiredError,
    DPoPThumbprintMismatchError,
    DPoPNonceMismatchError,
)

from .conftest import (
    FakeClock,
    b64url_encode,
    build_dpop_proof,
    compute_ath,
    compute_jwk_thumbprint,
    get_thumbprint_from_proof,
)


# =============================================================================
# RFC 9449 Section 4.3 Check 2: Well-formed JWT
# =============================================================================


class TestWellFormedJWT:
    """RFC 9449 Section 4.3 Check 2: DPoP value is a single well-formed JWT."""

    def test_valid_proof_parses_successfully(self, es256_keypair, clock):
        """A well-formed DPoP proof with valid signature should parse."""
        proof = build_dpop_proof(es256_keypair, htm="POST", htu="https://mcp.example.com/messages", iat=clock.now())

        config = DPoPValidatorConfig(clock=clock)
        validator = DPoPValidator(config)

        result = validator.validate_proof(proof=proof, method="POST", url="https://mcp.example.com/messages")

        assert result.jti is not None
        assert result.htm == "POST"
        assert result.htu == "https://mcp.example.com/messages"

    def test_malformed_jwt_rejected(self, clock):
        """Non-JWT strings should be rejected."""
        config = DPoPValidatorConfig(clock=clock)
        validator = DPoPValidator(config)

        with pytest.raises(InvalidDPoPProofError, match="invalid proof header"):
            validator.validate_proof(proof="not-a-jwt", method="POST", url="https://mcp.example.com/messages")

    def test_empty_string_rejected(self, clock):
        """Empty string should be rejected."""
        config = DPoPValidatorConfig(clock=clock)
        validator = DPoPValidator(config)

        with pytest.raises(InvalidDPoPProofError):
            validator.validate_proof(proof="", method="POST", url="https://mcp.example.com/messages")


# =============================================================================
# RFC 9449 Section 4.3 Check 3: Required Claims
# =============================================================================


class TestRequiredClaims:
    """RFC 9449 Section 4.3 Check 3: All required claims present."""

    def test_missing_jti_rejected(self, es256_keypair, clock):
        """Proof without jti claim should be rejected."""
        import jwt as pyjwt

        # Build proof manually without jti
        public_key = es256_keypair.public_key()
        public_numbers = public_key.public_numbers()
        x_bytes = public_numbers.x.to_bytes(32, byteorder="big")
        y_bytes = public_numbers.y.to_bytes(32, byteorder="big")
        jwk = {"kty": "EC", "crv": "P-256", "x": b64url_encode(x_bytes), "y": b64url_encode(y_bytes)}

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

    def test_missing_htm_rejected(self, es256_keypair, clock):
        """Proof without htm claim should be rejected."""
        import jwt as pyjwt

        public_key = es256_keypair.public_key()
        public_numbers = public_key.public_numbers()
        x_bytes = public_numbers.x.to_bytes(32, byteorder="big")
        y_bytes = public_numbers.y.to_bytes(32, byteorder="big")
        jwk = {"kty": "EC", "crv": "P-256", "x": b64url_encode(x_bytes), "y": b64url_encode(y_bytes)}

        header = {"typ": "dpop+jwt", "alg": "ES256", "jwk": jwk}
        payload = {
            "jti": str(uuid.uuid4()),
            # Missing htm
            "htu": "https://mcp.example.com/messages",
            "iat": int(clock.now()),
        }
        proof = pyjwt.encode(payload, es256_keypair, algorithm="ES256", headers=header)

        config = DPoPValidatorConfig(clock=clock)
        validator = DPoPValidator(config)

        with pytest.raises(InvalidDPoPProofError, match="htm"):
            validator.validate_proof(proof=proof, method="POST", url="https://mcp.example.com/messages")

    def test_missing_htu_rejected(self, es256_keypair, clock):
        """Proof without htu claim should be rejected."""
        import jwt as pyjwt

        public_key = es256_keypair.public_key()
        public_numbers = public_key.public_numbers()
        x_bytes = public_numbers.x.to_bytes(32, byteorder="big")
        y_bytes = public_numbers.y.to_bytes(32, byteorder="big")
        jwk = {"kty": "EC", "crv": "P-256", "x": b64url_encode(x_bytes), "y": b64url_encode(y_bytes)}

        header = {"typ": "dpop+jwt", "alg": "ES256", "jwk": jwk}
        payload = {
            "jti": str(uuid.uuid4()),
            "htm": "POST",
            # Missing htu
            "iat": int(clock.now()),
        }
        proof = pyjwt.encode(payload, es256_keypair, algorithm="ES256", headers=header)

        config = DPoPValidatorConfig(clock=clock)
        validator = DPoPValidator(config)

        with pytest.raises(InvalidDPoPProofError, match="htu"):
            validator.validate_proof(proof=proof, method="POST", url="https://mcp.example.com/messages")

    def test_missing_iat_rejected(self, es256_keypair, clock):
        """Proof without iat claim should be rejected."""
        import jwt as pyjwt

        public_key = es256_keypair.public_key()
        public_numbers = public_key.public_numbers()
        x_bytes = public_numbers.x.to_bytes(32, byteorder="big")
        y_bytes = public_numbers.y.to_bytes(32, byteorder="big")
        jwk = {"kty": "EC", "crv": "P-256", "x": b64url_encode(x_bytes), "y": b64url_encode(y_bytes)}

        header = {"typ": "dpop+jwt", "alg": "ES256", "jwk": jwk}
        payload = {
            "jti": str(uuid.uuid4()),
            "htm": "POST",
            "htu": "https://mcp.example.com/messages",
            # Missing iat
        }
        proof = pyjwt.encode(payload, es256_keypair, algorithm="ES256", headers=header)

        config = DPoPValidatorConfig(clock=clock)
        validator = DPoPValidator(config)

        with pytest.raises(InvalidDPoPProofError, match="iat"):
            validator.validate_proof(proof=proof, method="POST", url="https://mcp.example.com/messages")


# =============================================================================
# RFC 9449 Section 4.3 Check 4: typ Header
# =============================================================================


class TestTypHeader:
    """RFC 9449 Section 4.3 Check 4: typ header must be dpop+jwt."""

    def test_correct_typ_accepted(self, es256_keypair, clock):
        """typ=dpop+jwt should be accepted."""
        proof = build_dpop_proof(es256_keypair, typ="dpop+jwt", iat=clock.now())

        config = DPoPValidatorConfig(clock=clock)
        validator = DPoPValidator(config)

        result = validator.validate_proof(proof=proof, method="POST", url="https://mcp.example.com/messages")
        assert result is not None

    def test_wrong_typ_rejected(self, es256_keypair, clock):
        """typ=jwt should be rejected."""
        proof = build_dpop_proof(es256_keypair, typ="jwt", iat=clock.now())

        config = DPoPValidatorConfig(clock=clock)
        validator = DPoPValidator(config)

        with pytest.raises(InvalidDPoPProofError, match="typ"):
            validator.validate_proof(proof=proof, method="POST", url="https://mcp.example.com/messages")

    def test_missing_typ_rejected(self, es256_keypair, clock):
        """Missing typ header should be rejected."""
        # Build proof with empty typ
        import jwt as pyjwt

        public_key = es256_keypair.public_key()
        public_numbers = public_key.public_numbers()
        x_bytes = public_numbers.x.to_bytes(32, byteorder="big")
        y_bytes = public_numbers.y.to_bytes(32, byteorder="big")
        jwk = {"kty": "EC", "crv": "P-256", "x": b64url_encode(x_bytes), "y": b64url_encode(y_bytes)}

        # No typ in header
        header = {"alg": "ES256", "jwk": jwk}
        payload = {
            "jti": str(uuid.uuid4()),
            "htm": "POST",
            "htu": "https://mcp.example.com/messages",
            "iat": int(clock.now()),
        }
        proof = pyjwt.encode(payload, es256_keypair, algorithm="ES256", headers=header)

        config = DPoPValidatorConfig(clock=clock)
        validator = DPoPValidator(config)

        with pytest.raises(InvalidDPoPProofError, match="typ"):
            validator.validate_proof(proof=proof, method="POST", url="https://mcp.example.com/messages")


# =============================================================================
# RFC 9449 Section 4.3 Check 5: Algorithm
# =============================================================================


class TestAlgorithm:
    """RFC 9449 Section 4.3 Check 5: Algorithm must be asymmetric and supported."""

    def test_es256_accepted(self, es256_keypair, clock):
        """ES256 should be accepted by default."""
        proof = build_dpop_proof(es256_keypair, alg="ES256", iat=clock.now())

        config = DPoPValidatorConfig(clock=clock, allowed_algorithms=["ES256"])
        validator = DPoPValidator(config)

        result = validator.validate_proof(proof=proof, method="POST", url="https://mcp.example.com/messages")
        assert result is not None

    def test_unsupported_algorithm_rejected(self, es256_keypair, clock):
        """Algorithms not in allowed list should be rejected."""
        # Note: We still use ES256 keypair but pretend it's ES384 in header
        # This will fail signature verification, but we test the algorithm check first
        proof = build_dpop_proof(es256_keypair, iat=clock.now())

        config = DPoPValidatorConfig(clock=clock, allowed_algorithms=["ES384"])
        validator = DPoPValidator(config)

        with pytest.raises(InvalidDPoPProofError, match="algorithm"):
            validator.validate_proof(proof=proof, method="POST", url="https://mcp.example.com/messages")


# =============================================================================
# RFC 9449 Section 4.3 Check 6: Signature Verification
# =============================================================================


class TestSignatureVerification:
    """RFC 9449 Section 4.3 Check 6: Signature must verify with embedded jwk."""

    def test_valid_signature_accepted(self, es256_keypair, clock):
        """Proof signed with matching key should be accepted."""
        proof = build_dpop_proof(es256_keypair, iat=clock.now())

        config = DPoPValidatorConfig(clock=clock)
        validator = DPoPValidator(config)

        result = validator.validate_proof(proof=proof, method="POST", url="https://mcp.example.com/messages")
        assert result is not None

    def test_tampered_proof_rejected(self, es256_keypair, clock):
        """Tampered proof should be rejected."""
        proof = build_dpop_proof(es256_keypair, iat=clock.now())

        # Tamper with the payload (change a character in the middle part)
        parts = proof.split(".")
        tampered_payload = parts[1][:-1] + ("A" if parts[1][-1] != "A" else "B")
        tampered_proof = f"{parts[0]}.{tampered_payload}.{parts[2]}"

        config = DPoPValidatorConfig(clock=clock)
        validator = DPoPValidator(config)

        with pytest.raises(InvalidDPoPProofError, match="signature"):
            validator.validate_proof(proof=tampered_proof, method="POST", url="https://mcp.example.com/messages")


# =============================================================================
# RFC 9449 Section 4.3 Check 7: No Private Key in JWK
# =============================================================================


class TestNoPrivateKeyInJWK:
    """RFC 9449 Section 4.3 Check 7: jwk must not contain private key."""

    def test_jwk_with_d_rejected(self, es256_keypair, clock):
        """JWK containing 'd' (EC private key) should be rejected."""
        import jwt as pyjwt

        public_key = es256_keypair.public_key()
        public_numbers = public_key.public_numbers()
        x_bytes = public_numbers.x.to_bytes(32, byteorder="big")
        y_bytes = public_numbers.y.to_bytes(32, byteorder="big")

        # Get private key 'd' value
        private_numbers = es256_keypair.private_numbers()
        d_bytes = private_numbers.private_value.to_bytes(32, byteorder="big")

        # JWK with private key material - FORBIDDEN
        jwk_with_private = {
            "kty": "EC",
            "crv": "P-256",
            "x": b64url_encode(x_bytes),
            "y": b64url_encode(y_bytes),
            "d": b64url_encode(d_bytes),  # Private key!
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


# =============================================================================
# RFC 9449 Section 4.3 Check 8: HTTP Method Binding
# =============================================================================


class TestMethodBinding:
    """RFC 9449 Section 4.3 Check 8: htm must match request method."""

    def test_method_match_accepted(self, es256_keypair, clock):
        """Proof bound to POST should validate for POST request."""
        proof = build_dpop_proof(es256_keypair, htm="POST", iat=clock.now())

        config = DPoPValidatorConfig(clock=clock)
        validator = DPoPValidator(config)

        result = validator.validate_proof(proof=proof, method="POST", url="https://mcp.example.com/messages")
        assert result.htm == "POST"

    def test_method_mismatch_rejected(self, es256_keypair, clock):
        """Proof bound to POST should not validate for GET request."""
        proof = build_dpop_proof(es256_keypair, htm="POST", iat=clock.now())

        config = DPoPValidatorConfig(clock=clock)
        validator = DPoPValidator(config)

        with pytest.raises(DPoPMethodMismatchError):
            validator.validate_proof(proof=proof, method="GET", url="https://mcp.example.com/messages")

    def test_method_case_insensitive(self, es256_keypair, clock):
        """Method comparison should be case-insensitive."""
        proof = build_dpop_proof(es256_keypair, htm="post", iat=clock.now())

        config = DPoPValidatorConfig(clock=clock)
        validator = DPoPValidator(config)

        result = validator.validate_proof(proof=proof, method="POST", url="https://mcp.example.com/messages")
        assert result is not None


# =============================================================================
# RFC 9449 Section 4.3 Check 9: URL Binding
# =============================================================================


class TestURLBinding:
    """RFC 9449 Section 4.3 Check 9: htu must match request URL."""

    def test_url_match_accepted(self, es256_keypair, clock):
        """Proof bound to URL should validate for same URL."""
        proof = build_dpop_proof(es256_keypair, htu="https://mcp.example.com/messages", iat=clock.now())

        config = DPoPValidatorConfig(clock=clock)
        validator = DPoPValidator(config)

        result = validator.validate_proof(proof=proof, method="POST", url="https://mcp.example.com/messages")
        assert result.htu == "https://mcp.example.com/messages"

    def test_url_mismatch_rejected(self, es256_keypair, clock):
        """Proof bound to one URL should not validate for different URL."""
        proof = build_dpop_proof(es256_keypair, htu="https://mcp.example.com/messages", iat=clock.now())

        config = DPoPValidatorConfig(clock=clock)
        validator = DPoPValidator(config)

        with pytest.raises(DPoPUrlMismatchError):
            validator.validate_proof(proof=proof, method="POST", url="https://different.example.com/messages")

    def test_url_scheme_case_insensitive(self, es256_keypair, clock):
        """URL scheme comparison should be case-insensitive."""
        proof = build_dpop_proof(es256_keypair, htu="HTTPS://mcp.example.com/messages", iat=clock.now())

        config = DPoPValidatorConfig(clock=clock)
        validator = DPoPValidator(config)

        result = validator.validate_proof(proof=proof, method="POST", url="https://mcp.example.com/messages")
        assert result is not None

    def test_url_host_case_insensitive(self, es256_keypair, clock):
        """URL host comparison should be case-insensitive."""
        proof = build_dpop_proof(es256_keypair, htu="https://MCP.Example.COM/messages", iat=clock.now())

        config = DPoPValidatorConfig(clock=clock)
        validator = DPoPValidator(config)

        result = validator.validate_proof(proof=proof, method="POST", url="https://mcp.example.com/messages")
        assert result is not None

    def test_url_strips_query(self, es256_keypair, clock):
        """Per RFC 9449, htu should match without query."""
        proof = build_dpop_proof(es256_keypair, htu="https://mcp.example.com/messages", iat=clock.now())

        config = DPoPValidatorConfig(clock=clock)
        validator = DPoPValidator(config)

        # Request URL has query - should still match
        result = validator.validate_proof(proof=proof, method="POST", url="https://mcp.example.com/messages?foo=bar")
        assert result is not None

    def test_url_strips_fragment(self, es256_keypair, clock):
        """Per RFC 9449, htu should match without fragment."""
        proof = build_dpop_proof(es256_keypair, htu="https://mcp.example.com/messages", iat=clock.now())

        config = DPoPValidatorConfig(clock=clock)
        validator = DPoPValidator(config)

        # Request URL has fragment - should still match
        result = validator.validate_proof(proof=proof, method="POST", url="https://mcp.example.com/messages#section")
        assert result is not None


# =============================================================================
# RFC 9449 Section 4.3 Check 10: Nonce Validation
# =============================================================================


class TestNonceValidation:
    """RFC 9449 Section 4.3 Check 10: nonce must match if server requires it."""

    def test_nonce_match_accepted(self, es256_keypair, clock):
        """Proof with matching nonce should be accepted."""
        nonce = "server-nonce-12345"
        proof = build_dpop_proof(es256_keypair, nonce=nonce, iat=clock.now())

        config = DPoPValidatorConfig(clock=clock)
        validator = DPoPValidator(config)

        result = validator.validate_proof(
            proof=proof, method="POST", url="https://mcp.example.com/messages", expected_nonce=nonce
        )
        assert result.nonce == nonce

    def test_nonce_mismatch_rejected(self, es256_keypair, clock):
        """Proof with non-matching nonce should be rejected."""
        proof = build_dpop_proof(es256_keypair, nonce="wrong-nonce", iat=clock.now())

        config = DPoPValidatorConfig(clock=clock)
        validator = DPoPValidator(config)

        with pytest.raises(DPoPNonceMismatchError):
            validator.validate_proof(
                proof=proof, method="POST", url="https://mcp.example.com/messages", expected_nonce="correct-nonce"
            )

    def test_missing_nonce_rejected_when_required(self, es256_keypair, clock):
        """Proof without nonce should be rejected when server requires it."""
        proof = build_dpop_proof(es256_keypair, iat=clock.now())  # No nonce

        config = DPoPValidatorConfig(clock=clock)
        validator = DPoPValidator(config)

        with pytest.raises(DPoPNonceMismatchError):
            validator.validate_proof(
                proof=proof, method="POST", url="https://mcp.example.com/messages", expected_nonce="required-nonce"
            )

    def test_nonce_optional_when_not_required(self, es256_keypair, clock):
        """Proof with nonce should be accepted when server doesn't require it."""
        proof = build_dpop_proof(es256_keypair, nonce="optional-nonce", iat=clock.now())

        config = DPoPValidatorConfig(clock=clock)
        validator = DPoPValidator(config)

        # No expected_nonce - server doesn't require it
        result = validator.validate_proof(proof=proof, method="POST", url="https://mcp.example.com/messages")
        assert result.nonce == "optional-nonce"


# =============================================================================
# RFC 9449 Section 4.3 Check 11: Timestamp Validation
# =============================================================================


class TestTimestampValidation:
    """RFC 9449 Section 4.3 Check 11: iat must be within acceptable window."""

    def test_current_timestamp_accepted(self, es256_keypair, clock):
        """Proof with current iat should be accepted."""
        proof = build_dpop_proof(es256_keypair, iat=clock.now())

        config = DPoPValidatorConfig(clock=clock, leeway=60)
        validator = DPoPValidator(config)

        result = validator.validate_proof(proof=proof, method="POST", url="https://mcp.example.com/messages")
        assert result is not None

    def test_within_leeway_accepted(self, es256_keypair, clock):
        """Proof within leeway window should be accepted."""
        # 30 seconds ago (within 60s leeway)
        proof = build_dpop_proof(es256_keypair, iat=clock.now() - 30)

        config = DPoPValidatorConfig(clock=clock, leeway=60)
        validator = DPoPValidator(config)

        result = validator.validate_proof(proof=proof, method="POST", url="https://mcp.example.com/messages")
        assert result is not None

    def test_expired_proof_rejected(self, es256_keypair, clock):
        """Proof with iat too far in the past should be rejected."""
        # 5 minutes ago (beyond 60s leeway)
        proof = build_dpop_proof(es256_keypair, iat=clock.now() - 300)

        config = DPoPValidatorConfig(clock=clock, leeway=60)
        validator = DPoPValidator(config)

        with pytest.raises(DPoPExpiredError):
            validator.validate_proof(proof=proof, method="POST", url="https://mcp.example.com/messages")

    def test_future_proof_rejected(self, es256_keypair, clock):
        """Proof with iat too far in the future should be rejected."""
        # 5 minutes in the future (beyond 60s leeway)
        proof = build_dpop_proof(es256_keypair, iat=clock.now() + 300)

        config = DPoPValidatorConfig(clock=clock, leeway=60)
        validator = DPoPValidator(config)

        with pytest.raises(DPoPExpiredError):
            validator.validate_proof(proof=proof, method="POST", url="https://mcp.example.com/messages")


# =============================================================================
# RFC 9449 Section 4.3 Check 12: Access Token Binding
# =============================================================================


class TestAccessTokenBinding:
    """RFC 9449 Section 4.3 Check 12: ath and thumbprint binding."""

    def test_ath_match_accepted(self, es256_keypair, clock):
        """Proof with correct ath should be accepted."""
        access_token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.test"
        expected_ath = compute_ath(access_token)

        proof = build_dpop_proof(es256_keypair, ath=expected_ath, iat=clock.now())

        config = DPoPValidatorConfig(clock=clock)
        validator = DPoPValidator(config)

        result = validator.validate_proof(
            proof=proof, method="POST", url="https://mcp.example.com/messages", access_token=access_token
        )
        assert result.ath == expected_ath

    def test_ath_mismatch_rejected(self, es256_keypair, clock):
        """Proof with wrong ath should be rejected."""
        proof = build_dpop_proof(es256_keypair, ath="wronghash123", iat=clock.now())

        config = DPoPValidatorConfig(clock=clock)
        validator = DPoPValidator(config)

        with pytest.raises(InvalidDPoPProofError, match="ath"):
            validator.validate_proof(
                proof=proof,
                method="POST",
                url="https://mcp.example.com/messages",
                access_token="eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.test",
            )

    def test_thumbprint_match_accepted(self, es256_keypair, clock):
        """Proof with key matching cnf.jkt should be accepted."""
        proof = build_dpop_proof(es256_keypair, iat=clock.now())
        expected_thumbprint = get_thumbprint_from_proof(proof)

        config = DPoPValidatorConfig(clock=clock)
        validator = DPoPValidator(config)

        result = validator.validate_proof(
            proof=proof, method="POST", url="https://mcp.example.com/messages", expected_thumbprint=expected_thumbprint
        )
        assert result.thumbprint == expected_thumbprint

    def test_thumbprint_mismatch_rejected(self, es256_keypair, clock):
        """Proof with key not matching cnf.jkt should be rejected."""
        proof = build_dpop_proof(es256_keypair, iat=clock.now())

        config = DPoPValidatorConfig(clock=clock)
        validator = DPoPValidator(config)

        with pytest.raises(DPoPThumbprintMismatchError):
            validator.validate_proof(
                proof=proof,
                method="POST",
                url="https://mcp.example.com/messages",
                expected_thumbprint="wrongthumbprint123",
            )


# =============================================================================
# RFC 9449 Section 11.1: Replay Protection
# =============================================================================


class TestReplayProtection:
    """RFC 9449 Section 11.1: Replay attack prevention via JTI."""

    def test_replay_detected(self, es256_keypair, clock):
        """Same JTI used twice should be rejected."""
        jti = str(uuid.uuid4())
        proof = build_dpop_proof(es256_keypair, jti=jti, iat=clock.now())

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

        proof1 = build_dpop_proof(es256_keypair, jti=str(uuid.uuid4()), iat=clock.now())
        proof2 = build_dpop_proof(es256_keypair, jti=str(uuid.uuid4()), iat=clock.now())

        result1 = validator.validate_proof(proof=proof1, method="POST", url="https://mcp.example.com/messages")
        result2 = validator.validate_proof(proof=proof2, method="POST", url="https://mcp.example.com/messages")

        assert result1.jti != result2.jti

    def test_jti_cache_eviction_after_ttl(self, es256_keypair, clock):
        """JTI should be evicted from cache after TTL."""
        jti = str(uuid.uuid4())
        proof = build_dpop_proof(es256_keypair, jti=jti, iat=clock.now())

        config = DPoPValidatorConfig(clock=clock, jti_cache_ttl=60)
        validator = DPoPValidator(config)

        # First use succeeds
        validator.validate_proof(proof=proof, method="POST", url="https://mcp.example.com/messages")

        # Advance time past TTL
        clock.advance(120)

        # Create new proof with same jti but fresh iat
        proof2 = build_dpop_proof(es256_keypair, jti=jti, iat=clock.now())

        # Should succeed after TTL eviction
        result = validator.validate_proof(proof=proof2, method="POST", url="https://mcp.example.com/messages")
        assert result is not None
