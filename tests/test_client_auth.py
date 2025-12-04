# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Tests for client-side authentication (DPoP, Bearer)."""

from __future__ import annotations

import base64
import hashlib
import json
import time
from typing import TYPE_CHECKING

import httpx
import jwt
import pytest
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import ec

from dedalus_mcp.client.auth import (
    BearerAuth,
    DPoPAuth,
    _b64url_encode,
    _compute_ath,
    _compute_jwk_thumbprint,
    generate_dpop_proof,
)

if TYPE_CHECKING:
    from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePrivateKey


@pytest.fixture
def es256_keypair() -> EllipticCurvePrivateKey:
    """Generate a fresh ES256 keypair for testing."""
    return ec.generate_private_key(ec.SECP256R1(), default_backend())


class TestGenerateDPoPProof:
    """Tests for generate_dpop_proof()."""

    def test_proof_is_valid_jwt(self, es256_keypair: EllipticCurvePrivateKey) -> None:
        """DPoP proof should be a valid JWT."""
        proof = generate_dpop_proof(es256_keypair, "POST", "https://api.example.com/mcp")

        # Should be decodable
        decoded = jwt.decode(proof, options={"verify_signature": False})
        assert "jti" in decoded
        assert "htm" in decoded
        assert "htu" in decoded
        assert "iat" in decoded

    def test_proof_has_correct_header(self, es256_keypair: EllipticCurvePrivateKey) -> None:
        """DPoP proof header should have typ=dpop+jwt, alg=ES256, jwk."""
        proof = generate_dpop_proof(es256_keypair, "GET", "https://example.com")

        # Decode header
        header_b64 = proof.split(".")[0]
        # Add padding if needed
        padding = 4 - len(header_b64) % 4
        if padding != 4:
            header_b64 += "=" * padding
        header = json.loads(base64.urlsafe_b64decode(header_b64))

        assert header["typ"] == "dpop+jwt"
        assert header["alg"] == "ES256"
        assert "jwk" in header
        assert header["jwk"]["kty"] == "EC"
        assert header["jwk"]["crv"] == "P-256"

    def test_proof_htm_matches_method(self, es256_keypair: EllipticCurvePrivateKey) -> None:
        """htm claim should match the HTTP method."""
        proof_get = generate_dpop_proof(es256_keypair, "GET", "https://example.com")
        proof_post = generate_dpop_proof(es256_keypair, "POST", "https://example.com")
        proof_lower = generate_dpop_proof(es256_keypair, "post", "https://example.com")

        decoded_get = jwt.decode(proof_get, options={"verify_signature": False})
        decoded_post = jwt.decode(proof_post, options={"verify_signature": False})
        decoded_lower = jwt.decode(proof_lower, options={"verify_signature": False})

        assert decoded_get["htm"] == "GET"
        assert decoded_post["htm"] == "POST"
        assert decoded_lower["htm"] == "POST"  # Uppercased

    def test_proof_htu_strips_query_and_fragment(self, es256_keypair: EllipticCurvePrivateKey) -> None:
        """htu claim should strip query and fragment per RFC 9449 §4.2."""
        proof = generate_dpop_proof(
            es256_keypair,
            "GET",
            "https://example.com/path?query=value#fragment",
        )

        decoded = jwt.decode(proof, options={"verify_signature": False})
        assert decoded["htu"] == "https://example.com/path"

    def test_proof_includes_ath_when_token_provided(self, es256_keypair: EllipticCurvePrivateKey) -> None:
        """ath claim should be present when access_token is provided."""
        access_token = "test_access_token_123"
        proof = generate_dpop_proof(
            es256_keypair,
            "POST",
            "https://example.com/mcp",
            access_token=access_token,
        )

        decoded = jwt.decode(proof, options={"verify_signature": False})
        assert "ath" in decoded

        # Verify ath is correct hash
        expected_ath = _compute_ath(access_token)
        assert decoded["ath"] == expected_ath

    def test_proof_excludes_ath_when_no_token(self, es256_keypair: EllipticCurvePrivateKey) -> None:
        """ath claim should be absent when access_token is not provided."""
        proof = generate_dpop_proof(es256_keypair, "POST", "https://example.com/mcp")

        decoded = jwt.decode(proof, options={"verify_signature": False})
        assert "ath" not in decoded

    def test_proof_includes_nonce_when_provided(self, es256_keypair: EllipticCurvePrivateKey) -> None:
        """nonce claim should be included when provided."""
        proof = generate_dpop_proof(
            es256_keypair,
            "POST",
            "https://example.com/mcp",
            nonce="server_nonce_abc",
        )

        decoded = jwt.decode(proof, options={"verify_signature": False})
        assert decoded["nonce"] == "server_nonce_abc"

    def test_proof_jti_is_unique(self, es256_keypair: EllipticCurvePrivateKey) -> None:
        """Each proof should have a unique jti."""
        proofs = [
            generate_dpop_proof(es256_keypair, "POST", "https://example.com")
            for _ in range(10)
        ]

        jtis = [jwt.decode(p, options={"verify_signature": False})["jti"] for p in proofs]
        assert len(set(jtis)) == 10  # All unique

    def test_proof_iat_is_current(self, es256_keypair: EllipticCurvePrivateKey) -> None:
        """iat claim should be close to current time."""
        before = int(time.time())
        proof = generate_dpop_proof(es256_keypair, "POST", "https://example.com")
        after = int(time.time())

        decoded = jwt.decode(proof, options={"verify_signature": False})
        assert before <= decoded["iat"] <= after

    def test_proof_signature_verifies(self, es256_keypair: EllipticCurvePrivateKey) -> None:
        """DPoP proof signature should verify with the embedded key."""
        proof = generate_dpop_proof(es256_keypair, "POST", "https://example.com")

        # Extract public key and verify
        public_key = es256_keypair.public_key()
        decoded = jwt.decode(proof, public_key, algorithms=["ES256"])
        assert decoded["htm"] == "POST"


class TestDPoPAuth:
    """Tests for DPoPAuth httpx.Auth implementation."""

    def test_auth_adds_authorization_header(self, es256_keypair: EllipticCurvePrivateKey) -> None:
        """DPoPAuth should add Authorization: DPoP header."""
        auth = DPoPAuth(access_token="test_token", dpop_key=es256_keypair)
        request = httpx.Request("POST", "https://example.com/mcp")

        # Run auth flow
        flow = auth.auth_flow(request)
        modified_request = next(flow)

        assert "Authorization" in modified_request.headers
        assert modified_request.headers["Authorization"] == "DPoP test_token"

    def test_auth_adds_dpop_header(self, es256_keypair: EllipticCurvePrivateKey) -> None:
        """DPoPAuth should add DPoP header with proof JWT."""
        auth = DPoPAuth(access_token="test_token", dpop_key=es256_keypair)
        request = httpx.Request("POST", "https://example.com/mcp")

        flow = auth.auth_flow(request)
        modified_request = next(flow)

        assert "DPoP" in modified_request.headers
        # Should be valid JWT
        proof = modified_request.headers["DPoP"]
        decoded = jwt.decode(proof, options={"verify_signature": False})
        assert decoded["htm"] == "POST"
        assert "https://example.com" in decoded["htu"]

    def test_auth_proof_includes_ath(self, es256_keypair: EllipticCurvePrivateKey) -> None:
        """DPoPAuth proof should include ath for the access token."""
        access_token = "my_access_token"
        auth = DPoPAuth(access_token=access_token, dpop_key=es256_keypair)
        request = httpx.Request("GET", "https://example.com/resource")

        flow = auth.auth_flow(request)
        modified_request = next(flow)

        proof = modified_request.headers["DPoP"]
        decoded = jwt.decode(proof, options={"verify_signature": False})
        assert decoded["ath"] == _compute_ath(access_token)

    def test_auth_proof_includes_nonce(self, es256_keypair: EllipticCurvePrivateKey) -> None:
        """DPoPAuth should include nonce when set."""
        auth = DPoPAuth(access_token="token", dpop_key=es256_keypair, nonce="initial_nonce")
        request = httpx.Request("POST", "https://example.com/mcp")

        flow = auth.auth_flow(request)
        modified_request = next(flow)

        proof = modified_request.headers["DPoP"]
        decoded = jwt.decode(proof, options={"verify_signature": False})
        assert decoded["nonce"] == "initial_nonce"

    def test_set_nonce_updates_proof(self, es256_keypair: EllipticCurvePrivateKey) -> None:
        """set_nonce() should update the nonce in subsequent proofs."""
        auth = DPoPAuth(access_token="token", dpop_key=es256_keypair)

        # First request - no nonce
        request1 = httpx.Request("POST", "https://example.com/mcp")
        flow1 = auth.auth_flow(request1)
        modified1 = next(flow1)
        proof1 = jwt.decode(modified1.headers["DPoP"], options={"verify_signature": False})
        assert "nonce" not in proof1

        # Update nonce
        auth.set_nonce("new_nonce")

        # Second request - has nonce
        request2 = httpx.Request("POST", "https://example.com/mcp")
        flow2 = auth.auth_flow(request2)
        modified2 = next(flow2)
        proof2 = jwt.decode(modified2.headers["DPoP"], options={"verify_signature": False})
        assert proof2["nonce"] == "new_nonce"

    def test_set_access_token_updates_auth(self, es256_keypair: EllipticCurvePrivateKey) -> None:
        """set_access_token() should update the token in subsequent requests."""
        auth = DPoPAuth(access_token="old_token", dpop_key=es256_keypair)

        # First request
        request1 = httpx.Request("POST", "https://example.com/mcp")
        flow1 = auth.auth_flow(request1)
        modified1 = next(flow1)
        assert modified1.headers["Authorization"] == "DPoP old_token"

        # Update token
        auth.set_access_token("new_token")

        # Second request
        request2 = httpx.Request("POST", "https://example.com/mcp")
        flow2 = auth.auth_flow(request2)
        modified2 = next(flow2)
        assert modified2.headers["Authorization"] == "DPoP new_token"

    def test_thumbprint_property(self, es256_keypair: EllipticCurvePrivateKey) -> None:
        """thumbprint property should return JWK thumbprint."""
        auth = DPoPAuth(access_token="token", dpop_key=es256_keypair)

        thumbprint = auth.thumbprint
        assert isinstance(thumbprint, str)
        assert len(thumbprint) > 20  # Base64url-encoded SHA-256 is 43 chars

        # Should match what we compute directly
        expected = _compute_jwk_thumbprint(es256_keypair.public_key())
        assert thumbprint == expected


class TestBearerAuth:
    """Tests for BearerAuth httpx.Auth implementation."""

    def test_auth_adds_bearer_header(self) -> None:
        """BearerAuth should add Authorization: Bearer header."""
        auth = BearerAuth(access_token="my_token")
        request = httpx.Request("GET", "https://example.com/resource")

        flow = auth.auth_flow(request)
        modified_request = next(flow)

        assert modified_request.headers["Authorization"] == "Bearer my_token"

    def test_set_access_token_updates_header(self) -> None:
        """set_access_token() should update subsequent requests."""
        auth = BearerAuth(access_token="old_token")

        # First request
        request1 = httpx.Request("GET", "https://example.com")
        flow1 = auth.auth_flow(request1)
        modified1 = next(flow1)
        assert modified1.headers["Authorization"] == "Bearer old_token"

        # Update
        auth.set_access_token("new_token")

        # Second request
        request2 = httpx.Request("GET", "https://example.com")
        flow2 = auth.auth_flow(request2)
        modified2 = next(flow2)
        assert modified2.headers["Authorization"] == "Bearer new_token"


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_b64url_encode_no_padding(self) -> None:
        """_b64url_encode should not include padding."""
        result = _b64url_encode(b"test")
        assert "=" not in result

    def test_compute_ath(self) -> None:
        """_compute_ath should return base64url(sha256(token))."""
        token = "test_token"
        result = _compute_ath(token)

        # Manual computation
        expected_hash = hashlib.sha256(token.encode()).digest()
        expected = base64.urlsafe_b64encode(expected_hash).rstrip(b"=").decode()

        assert result == expected

    def test_compute_jwk_thumbprint(self, es256_keypair: EllipticCurvePrivateKey) -> None:
        """_compute_jwk_thumbprint should match RFC 7638."""
        public_key = es256_keypair.public_key()
        thumbprint = _compute_jwk_thumbprint(public_key)

        # Should be base64url-encoded SHA-256 (43 chars without padding)
        assert isinstance(thumbprint, str)
        assert len(thumbprint) == 43

        # Should be deterministic
        assert _compute_jwk_thumbprint(public_key) == thumbprint


class TestDPoPAuthWithHTTPX:
    """Integration tests using httpx transport mock."""

    @pytest.mark.anyio
    async def test_dpop_auth_with_async_client(self, es256_keypair: EllipticCurvePrivateKey) -> None:
        """DPoPAuth should work with httpx.AsyncClient."""
        auth = DPoPAuth(access_token="integration_token", dpop_key=es256_keypair)

        # Create a mock transport that captures the request
        captured_requests: list[httpx.Request] = []

        class MockTransport(httpx.AsyncBaseTransport):
            async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
                captured_requests.append(request)
                return httpx.Response(200, json={"status": "ok"})

        async with httpx.AsyncClient(transport=MockTransport(), auth=auth) as client:
            await client.post("https://example.com/mcp", json={"test": True})

        assert len(captured_requests) == 1
        req = captured_requests[0]

        assert req.headers["Authorization"] == "DPoP integration_token"
        assert "DPoP" in req.headers

        # Verify proof
        proof = req.headers["DPoP"]
        decoded = jwt.decode(proof, options={"verify_signature": False})
        assert decoded["htm"] == "POST"
        assert "example.com" in decoded["htu"]

