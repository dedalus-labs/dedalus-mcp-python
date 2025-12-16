# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Tests for DPoP proof generation per RFC 9449 Section 4.2.

These tests verify that generated proofs conform to RFC 9449 requirements:
- Header contains typ, alg, jwk
- Payload contains jti, htm, htu, iat
- Optional claims: ath, nonce
- URL normalization strips query/fragment
"""

from __future__ import annotations

import time
import jwt
import pytest

from dedalus_mcp.dpop import (
    generate_dpop_keypair,
    generate_dpop_proof,
    DPoPAuth,
    BearerAuth,
    compute_jwk_thumbprint,
    compute_access_token_hash,
)


class TestGenerateDPoPProof:
    """Tests for generate_dpop_proof() function."""

    def test_generates_valid_jwt(self, es256_keypair):
        """Generated proof should be a valid JWT."""
        proof = generate_dpop_proof(
            private_key=es256_keypair,
            method="POST",
            url="https://mcp.example.com/messages",
        )

        # Should be parseable as JWT
        header = jwt.get_unverified_header(proof)
        assert header is not None
        assert "typ" in header
        assert "alg" in header
        assert "jwk" in header

    def test_header_has_correct_typ(self, es256_keypair):
        """Header typ should be dpop+jwt per RFC 9449."""
        proof = generate_dpop_proof(
            private_key=es256_keypair,
            method="POST",
            url="https://mcp.example.com/messages",
        )

        header = jwt.get_unverified_header(proof)
        assert header["typ"] == "dpop+jwt"

    def test_header_has_es256_alg(self, es256_keypair):
        """Header alg should be ES256."""
        proof = generate_dpop_proof(
            private_key=es256_keypair,
            method="POST",
            url="https://mcp.example.com/messages",
        )

        header = jwt.get_unverified_header(proof)
        assert header["alg"] == "ES256"

    def test_header_has_public_jwk(self, es256_keypair):
        """Header jwk should contain public key (no private material)."""
        proof = generate_dpop_proof(
            private_key=es256_keypair,
            method="POST",
            url="https://mcp.example.com/messages",
        )

        header = jwt.get_unverified_header(proof)
        jwk = header["jwk"]

        assert jwk["kty"] == "EC"
        assert jwk["crv"] == "P-256"
        assert "x" in jwk
        assert "y" in jwk
        assert "d" not in jwk  # No private key

    def test_payload_has_required_claims(self, es256_keypair):
        """Payload should have jti, htm, htu, iat per RFC 9449."""
        proof = generate_dpop_proof(
            private_key=es256_keypair,
            method="POST",
            url="https://mcp.example.com/messages",
        )

        # Decode without verification (we're testing structure)
        header = jwt.get_unverified_header(proof)
        claims = jwt.decode(proof, options={"verify_signature": False})

        assert "jti" in claims
        assert "htm" in claims
        assert "htu" in claims
        assert "iat" in claims

    def test_htm_is_uppercase(self, es256_keypair):
        """htm should be uppercase HTTP method."""
        proof = generate_dpop_proof(
            private_key=es256_keypair,
            method="post",  # Lowercase input
            url="https://mcp.example.com/messages",
        )

        claims = jwt.decode(proof, options={"verify_signature": False})
        assert claims["htm"] == "POST"  # Uppercase output

    def test_htu_strips_query(self, es256_keypair):
        """htu should not include query parameters per RFC 9449."""
        proof = generate_dpop_proof(
            private_key=es256_keypair,
            method="POST",
            url="https://mcp.example.com/messages?foo=bar&baz=qux",
        )

        claims = jwt.decode(proof, options={"verify_signature": False})
        assert claims["htu"] == "https://mcp.example.com/messages"
        assert "?" not in claims["htu"]

    def test_htu_strips_fragment(self, es256_keypair):
        """htu should not include fragment per RFC 9449."""
        proof = generate_dpop_proof(
            private_key=es256_keypair,
            method="POST",
            url="https://mcp.example.com/messages#section",
        )

        claims = jwt.decode(proof, options={"verify_signature": False})
        assert claims["htu"] == "https://mcp.example.com/messages"
        assert "#" not in claims["htu"]

    def test_jti_is_unique(self, es256_keypair):
        """Each proof should have a unique jti."""
        proof1 = generate_dpop_proof(
            private_key=es256_keypair,
            method="POST",
            url="https://mcp.example.com/messages",
        )
        proof2 = generate_dpop_proof(
            private_key=es256_keypair,
            method="POST",
            url="https://mcp.example.com/messages",
        )

        claims1 = jwt.decode(proof1, options={"verify_signature": False})
        claims2 = jwt.decode(proof2, options={"verify_signature": False})

        assert claims1["jti"] != claims2["jti"]

    def test_iat_is_current_time(self, es256_keypair):
        """iat should be close to current time."""
        before = int(time.time())

        proof = generate_dpop_proof(
            private_key=es256_keypair,
            method="POST",
            url="https://mcp.example.com/messages",
        )

        after = int(time.time())

        claims = jwt.decode(proof, options={"verify_signature": False})
        assert before <= claims["iat"] <= after

    def test_ath_included_when_access_token_provided(self, es256_keypair):
        """ath claim should be present when access_token provided."""
        access_token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.test"

        proof = generate_dpop_proof(
            private_key=es256_keypair,
            method="POST",
            url="https://mcp.example.com/messages",
            access_token=access_token,
        )

        claims = jwt.decode(proof, options={"verify_signature": False})
        assert "ath" in claims
        assert claims["ath"] == compute_access_token_hash(access_token)

    def test_ath_not_included_without_access_token(self, es256_keypair):
        """ath claim should not be present when no access_token."""
        proof = generate_dpop_proof(
            private_key=es256_keypair,
            method="POST",
            url="https://mcp.example.com/messages",
        )

        claims = jwt.decode(proof, options={"verify_signature": False})
        assert "ath" not in claims

    def test_nonce_included_when_provided(self, es256_keypair):
        """nonce claim should be present when provided."""
        nonce = "server-nonce-12345"

        proof = generate_dpop_proof(
            private_key=es256_keypair,
            method="POST",
            url="https://mcp.example.com/messages",
            nonce=nonce,
        )

        claims = jwt.decode(proof, options={"verify_signature": False})
        assert claims["nonce"] == nonce

    def test_nonce_not_included_without_value(self, es256_keypair):
        """nonce claim should not be present when not provided."""
        proof = generate_dpop_proof(
            private_key=es256_keypair,
            method="POST",
            url="https://mcp.example.com/messages",
        )

        claims = jwt.decode(proof, options={"verify_signature": False})
        assert "nonce" not in claims

    def test_signature_verifies_with_embedded_key(self, es256_keypair):
        """Proof signature should verify with the embedded JWK."""
        from jwt.algorithms import ECAlgorithm
        import json

        proof = generate_dpop_proof(
            private_key=es256_keypair,
            method="POST",
            url="https://mcp.example.com/messages",
        )

        header = jwt.get_unverified_header(proof)
        jwk = header["jwk"]
        public_key = ECAlgorithm.from_jwk(json.dumps(jwk))

        # Should not raise
        claims = jwt.decode(proof, public_key, algorithms=["ES256"])
        assert claims["htm"] == "POST"


class TestGenerateDPoPKeypair:
    """Tests for generate_dpop_keypair() function."""

    def test_returns_private_key_and_jwk(self):
        """Should return (private_key, public_jwk) tuple."""
        private_key, public_jwk = generate_dpop_keypair()

        assert private_key is not None
        assert public_jwk is not None
        assert isinstance(public_jwk, dict)

    def test_jwk_has_required_fields(self):
        """Public JWK should have kty, crv, x, y."""
        _, public_jwk = generate_dpop_keypair()

        assert public_jwk["kty"] == "EC"
        assert public_jwk["crv"] == "P-256"
        assert "x" in public_jwk
        assert "y" in public_jwk

    def test_jwk_has_no_private_material(self):
        """Public JWK should not have d (private key)."""
        _, public_jwk = generate_dpop_keypair()

        assert "d" not in public_jwk

    def test_keypair_can_sign_and_verify(self):
        """Generated keypair should work for signing/verification."""
        private_key, public_jwk = generate_dpop_keypair()

        # Generate proof with private key
        proof = generate_dpop_proof(
            private_key=private_key,
            method="POST",
            url="https://example.com/token",
        )

        # Verify with public key
        from jwt.algorithms import ECAlgorithm
        import json

        public_key = ECAlgorithm.from_jwk(json.dumps(public_jwk))
        claims = jwt.decode(proof, public_key, algorithms=["ES256"])

        assert claims["htm"] == "POST"

    def test_thumbprint_consistent(self):
        """Thumbprint should be consistent for same key."""
        private_key, public_jwk = generate_dpop_keypair()

        thumbprint1 = compute_jwk_thumbprint(public_jwk)
        thumbprint2 = compute_jwk_thumbprint(public_jwk)

        assert thumbprint1 == thumbprint2

    def test_different_keypairs_have_different_thumbprints(self):
        """Different keypairs should have different thumbprints."""
        _, jwk1 = generate_dpop_keypair()
        _, jwk2 = generate_dpop_keypair()

        assert compute_jwk_thumbprint(jwk1) != compute_jwk_thumbprint(jwk2)


class TestDPoPAuth:
    """Tests for DPoPAuth httpx.Auth handler."""

    def test_adds_authorization_header(self, es256_keypair):
        """Should add Authorization: DPoP header."""
        import httpx

        auth = DPoPAuth(access_token="test-token", dpop_key=es256_keypair)
        request = httpx.Request("POST", "https://mcp.example.com/messages")

        # Get the modified request
        flow = auth.auth_flow(request)
        modified_request = next(flow)

        assert "Authorization" in modified_request.headers
        assert modified_request.headers["Authorization"].startswith("DPoP ")

    def test_adds_dpop_header(self, es256_keypair):
        """Should add DPoP header with proof JWT."""
        import httpx

        auth = DPoPAuth(access_token="test-token", dpop_key=es256_keypair)
        request = httpx.Request("POST", "https://mcp.example.com/messages")

        flow = auth.auth_flow(request)
        modified_request = next(flow)

        assert "DPoP" in modified_request.headers

        # Should be a valid JWT
        proof = modified_request.headers["DPoP"]
        header = jwt.get_unverified_header(proof)
        assert header["typ"] == "dpop+jwt"

    def test_proof_bound_to_request_method(self, es256_keypair):
        """Proof should be bound to request HTTP method."""
        import httpx

        auth = DPoPAuth(access_token="test-token", dpop_key=es256_keypair)
        request = httpx.Request("GET", "https://mcp.example.com/messages")

        flow = auth.auth_flow(request)
        modified_request = next(flow)

        proof = modified_request.headers["DPoP"]
        claims = jwt.decode(proof, options={"verify_signature": False})
        assert claims["htm"] == "GET"

    def test_proof_bound_to_request_url(self, es256_keypair):
        """Proof should be bound to request URL."""
        import httpx

        auth = DPoPAuth(access_token="test-token", dpop_key=es256_keypair)
        request = httpx.Request("POST", "https://mcp.example.com/messages")

        flow = auth.auth_flow(request)
        modified_request = next(flow)

        proof = modified_request.headers["DPoP"]
        claims = jwt.decode(proof, options={"verify_signature": False})
        assert claims["htu"] == "https://mcp.example.com/messages"

    def test_proof_includes_ath(self, es256_keypair):
        """Proof should include ath claim binding to access token."""
        import httpx

        access_token = "test-access-token"
        auth = DPoPAuth(access_token=access_token, dpop_key=es256_keypair)
        request = httpx.Request("POST", "https://mcp.example.com/messages")

        flow = auth.auth_flow(request)
        modified_request = next(flow)

        proof = modified_request.headers["DPoP"]
        claims = jwt.decode(proof, options={"verify_signature": False})
        assert claims["ath"] == compute_access_token_hash(access_token)

    def test_nonce_included_when_set(self, es256_keypair):
        """Proof should include nonce when set."""
        import httpx

        auth = DPoPAuth(access_token="test-token", dpop_key=es256_keypair, nonce="server-nonce")
        request = httpx.Request("POST", "https://mcp.example.com/messages")

        flow = auth.auth_flow(request)
        modified_request = next(flow)

        proof = modified_request.headers["DPoP"]
        claims = jwt.decode(proof, options={"verify_signature": False})
        assert claims["nonce"] == "server-nonce"

    def test_set_nonce_updates_proofs(self, es256_keypair):
        """set_nonce() should update subsequent proofs."""
        import httpx

        auth = DPoPAuth(access_token="test-token", dpop_key=es256_keypair)

        # First request - no nonce
        request1 = httpx.Request("POST", "https://mcp.example.com/messages")
        flow1 = auth.auth_flow(request1)
        modified1 = next(flow1)
        proof1 = modified1.headers["DPoP"]
        claims1 = jwt.decode(proof1, options={"verify_signature": False})
        assert "nonce" not in claims1

        # Set nonce
        auth.set_nonce("new-nonce")

        # Second request - should have nonce
        request2 = httpx.Request("POST", "https://mcp.example.com/messages")
        flow2 = auth.auth_flow(request2)
        modified2 = next(flow2)
        proof2 = modified2.headers["DPoP"]
        claims2 = jwt.decode(proof2, options={"verify_signature": False})
        assert claims2["nonce"] == "new-nonce"

    def test_thumbprint_property(self, es256_keypair):
        """thumbprint property should return key thumbprint."""
        auth = DPoPAuth(access_token="test-token", dpop_key=es256_keypair)

        thumbprint = auth.thumbprint
        assert thumbprint is not None
        assert len(thumbprint) == 43  # Base64url SHA-256


class TestBearerAuth:
    """Tests for BearerAuth httpx.Auth handler."""

    def test_adds_bearer_authorization(self):
        """Should add Authorization: Bearer header."""
        import httpx

        auth = BearerAuth(access_token="test-token")
        request = httpx.Request("GET", "https://api.example.com/resource")

        flow = auth.auth_flow(request)
        modified_request = next(flow)

        assert modified_request.headers["Authorization"] == "Bearer test-token"

    def test_no_dpop_header(self):
        """Should not add DPoP header."""
        import httpx

        auth = BearerAuth(access_token="test-token")
        request = httpx.Request("GET", "https://api.example.com/resource")

        flow = auth.auth_flow(request)
        modified_request = next(flow)

        assert "DPoP" not in modified_request.headers

    def test_set_access_token_updates_header(self):
        """set_access_token() should update subsequent requests."""
        import httpx

        auth = BearerAuth(access_token="old-token")

        # First request
        request1 = httpx.Request("GET", "https://api.example.com/resource")
        flow1 = auth.auth_flow(request1)
        modified1 = next(flow1)
        assert modified1.headers["Authorization"] == "Bearer old-token"

        # Update token
        auth.set_access_token("new-token")

        # Second request
        request2 = httpx.Request("GET", "https://api.example.com/resource")
        flow2 = auth.auth_flow(request2)
        modified2 = next(flow2)
        assert modified2.headers["Authorization"] == "Bearer new-token"
