# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Tests for DPoP middleware integration with AuthorizationManager."""

from __future__ import annotations

import base64
import hashlib
import json
import time
import uuid
from typing import Any

import pytest

pytest.importorskip("starlette")

from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient

from dedalus_mcp.server.authorization import (
    AuthorizationConfig,
    AuthorizationContext,
    AuthorizationManager,
    AuthorizationProvider,
)


def _b64url_encode(data: bytes) -> str:
    """Base64url encode without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _build_dpop_proof(
    private_key,
    *,
    htm: str = "POST",
    htu: str = "http://testserver/messages",
    iat: float | None = None,
    ath: str | None = None,
) -> str:
    """Build a DPoP proof JWT for testing."""
    import jwt

    public_key = private_key.public_key()
    public_numbers = public_key.public_numbers()
    x_bytes = public_numbers.x.to_bytes(32, byteorder="big")
    y_bytes = public_numbers.y.to_bytes(32, byteorder="big")

    jwk = {"kty": "EC", "crv": "P-256", "x": _b64url_encode(x_bytes), "y": _b64url_encode(y_bytes)}
    header = {"typ": "dpop+jwt", "alg": "ES256", "jwk": jwk}

    payload: dict[str, Any] = {
        "jti": str(uuid.uuid4()),
        "htm": htm,
        "htu": htu,
        "iat": int(iat if iat is not None else time.time()),
    }
    if ath is not None:
        payload["ath"] = ath

    return jwt.encode(payload, private_key, algorithm="ES256", headers=header)


def _compute_jwk_thumbprint(private_key) -> str:
    """Compute JWK thumbprint for binding."""
    public_key = private_key.public_key()
    public_numbers = public_key.public_numbers()
    x_bytes = public_numbers.x.to_bytes(32, byteorder="big")
    y_bytes = public_numbers.y.to_bytes(32, byteorder="big")
    jwk = {"kty": "EC", "crv": "P-256", "x": _b64url_encode(x_bytes), "y": _b64url_encode(y_bytes)}
    canonical = json.dumps(
        {"crv": jwk["crv"], "kty": jwk["kty"], "x": jwk["x"], "y": jwk["y"]}, separators=(",", ":"), sort_keys=True
    )
    return _b64url_encode(hashlib.sha256(canonical.encode()).digest())


class MockDPoPProvider(AuthorizationProvider):
    """Mock provider that validates DPoP-bound tokens."""

    def __init__(self, expected_thumbprint: str | None = None):
        self._expected_thumbprint = expected_thumbprint

    async def validate(self, token: str) -> AuthorizationContext:
        # Mock validation - just return context with cnf.jkt claim
        claims = {"sub": "user123", "scope": "mcp:tools:call"}
        if self._expected_thumbprint:
            claims["cnf"] = {"jkt": self._expected_thumbprint}
        return AuthorizationContext(subject="user123", scopes=["mcp:tools:call"], claims=claims)


@pytest.fixture
def es256_keypair():
    """Generate an ES256 key pair for testing."""
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.backends import default_backend

    return ec.generate_private_key(ec.SECP256R1(), default_backend())


class TestDPoPMiddleware:
    """Tests for DPoP middleware integration."""

    def test_dpop_required_rejects_bearer(self, es256_keypair):
        """When require_dpop=True, Bearer tokens should be rejected."""
        config = AuthorizationConfig(enabled=True, require_dpop=True)
        manager = AuthorizationManager(config, provider=MockDPoPProvider())

        async def handler(request):
            from starlette.responses import JSONResponse

            return JSONResponse({"status": "ok"})

        app = Starlette(routes=[Route("/messages", handler, methods=["POST"])])
        app = manager.wrap_asgi(app)

        client = TestClient(app, raise_server_exceptions=False)
        response = client.post("/messages", headers={"Authorization": "Bearer test_token"})

        assert response.status_code == 401
        assert "DPoP" in response.json().get("detail", "")

    def test_dpop_required_rejects_missing_proof(self, es256_keypair):
        """When require_dpop=True, missing DPoP header should be rejected."""
        config = AuthorizationConfig(enabled=True, require_dpop=True)
        manager = AuthorizationManager(config, provider=MockDPoPProvider())

        async def handler(request):
            from starlette.responses import JSONResponse

            return JSONResponse({"status": "ok"})

        app = Starlette(routes=[Route("/messages", handler, methods=["POST"])])
        app = manager.wrap_asgi(app)

        client = TestClient(app, raise_server_exceptions=False)
        # DPoP auth scheme but no DPoP proof header
        response = client.post("/messages", headers={"Authorization": "DPoP test_token"})

        assert response.status_code == 401
        assert "DPoP proof" in response.json().get("detail", "")

    def test_dpop_valid_proof_accepted(self, es256_keypair):
        """Valid DPoP proof should be accepted."""
        thumbprint = _compute_jwk_thumbprint(es256_keypair)
        config = AuthorizationConfig(enabled=True, require_dpop=True)
        manager = AuthorizationManager(config, provider=MockDPoPProvider(expected_thumbprint=thumbprint))

        async def handler(request):
            from starlette.responses import JSONResponse

            auth = request.scope.get("dedalus_mcp.auth")
            return JSONResponse({"subject": auth.subject if auth else None})

        app = Starlette(routes=[Route("/messages", handler, methods=["POST"])])
        app = manager.wrap_asgi(app)

        access_token = "test_access_token"
        ath = _b64url_encode(hashlib.sha256(access_token.encode()).digest())
        proof = _build_dpop_proof(es256_keypair, htm="POST", htu="http://testserver/messages", ath=ath)

        client = TestClient(app, raise_server_exceptions=False)
        response = client.post("/messages", headers={"Authorization": f"DPoP {access_token}", "DPoP": proof})

        assert response.status_code == 200
        assert response.json()["subject"] == "user123"

    def test_dpop_invalid_proof_rejected(self, es256_keypair):
        """Invalid DPoP proof (wrong method) should be rejected."""
        thumbprint = _compute_jwk_thumbprint(es256_keypair)
        config = AuthorizationConfig(enabled=True, require_dpop=True)
        manager = AuthorizationManager(config, provider=MockDPoPProvider(expected_thumbprint=thumbprint))

        async def handler(request):
            from starlette.responses import JSONResponse

            return JSONResponse({"status": "ok"})

        app = Starlette(routes=[Route("/messages", handler, methods=["POST"])])
        app = manager.wrap_asgi(app)

        access_token = "test_access_token"
        ath = _b64url_encode(hashlib.sha256(access_token.encode()).digest())
        # Wrong method - proof says GET but request is POST
        proof = _build_dpop_proof(es256_keypair, htm="GET", htu="http://testserver/messages", ath=ath)

        client = TestClient(app, raise_server_exceptions=False)
        response = client.post("/messages", headers={"Authorization": f"DPoP {access_token}", "DPoP": proof})

        assert response.status_code == 401
        assert "DPoP" in response.json().get("detail", "")

    def test_bearer_mode_ignores_dpop(self, es256_keypair):
        """When require_dpop=False, Bearer tokens should work normally."""
        config = AuthorizationConfig(enabled=True, require_dpop=False)
        manager = AuthorizationManager(config, provider=MockDPoPProvider())

        async def handler(request):
            from starlette.responses import JSONResponse

            auth = request.scope.get("dedalus_mcp.auth")
            return JSONResponse({"subject": auth.subject if auth else None})

        app = Starlette(routes=[Route("/messages", handler, methods=["POST"])])
        app = manager.wrap_asgi(app)

        client = TestClient(app, raise_server_exceptions=False)
        response = client.post("/messages", headers={"Authorization": "Bearer test_token"})

        assert response.status_code == 200
        assert response.json()["subject"] == "user123"
