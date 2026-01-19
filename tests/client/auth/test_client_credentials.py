# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Tests for OAuth 2.0 Client Credentials Auth (RFC 6749 Section 4.4).

ClientCredentialsAuth is the primary auth mechanism for M2M (machine-to-machine)
communication, CI/CD pipelines, and backend services.
"""

from __future__ import annotations

import pytest
import httpx
import respx


# =============================================================================
# ClientCredentialsAuth Construction Tests
# =============================================================================


class TestClientCredentialsAuthConstruction:
    """Tests for ClientCredentialsAuth initialization."""

    def test_construction_with_server_metadata(self):
        """ClientCredentialsAuth can be constructed with AS metadata."""
        from dedalus_mcp.client.auth.client_credentials import ClientCredentialsAuth
        from dedalus_mcp.client.auth.models import AuthorizationServerMetadata

        server_metadata = AuthorizationServerMetadata(
            issuer="https://as.example.com",
            token_endpoint="https://as.example.com/oauth2/token",
            grant_types_supported=["client_credentials"],
        )

        auth = ClientCredentialsAuth(server_metadata=server_metadata, client_id="m2m", client_secret="secret123")

        assert auth.client_id == "m2m"
        assert auth.token_endpoint == "https://as.example.com/oauth2/token"

    def test_construction_validates_grant_type_support(self):
        """ClientCredentialsAuth raises if AS doesn't support client_credentials."""
        from dedalus_mcp.client.auth.client_credentials import ClientCredentialsAuth, AuthConfigError
        from dedalus_mcp.client.auth.models import AuthorizationServerMetadata

        server_metadata = AuthorizationServerMetadata(
            issuer="https://as.example.com",
            token_endpoint="https://as.example.com/oauth2/token",
            grant_types_supported=["authorization_code"],  # No client_credentials
        )

        with pytest.raises(AuthConfigError, match="client_credentials"):
            ClientCredentialsAuth(server_metadata=server_metadata, client_id="m2m", client_secret="secret123")

    def test_construction_with_scope(self):
        """ClientCredentialsAuth accepts optional scope parameter."""
        from dedalus_mcp.client.auth.client_credentials import ClientCredentialsAuth
        from dedalus_mcp.client.auth.models import AuthorizationServerMetadata

        server_metadata = AuthorizationServerMetadata(
            issuer="https://as.example.com",
            token_endpoint="https://as.example.com/oauth2/token",
            grant_types_supported=["client_credentials"],
        )

        auth = ClientCredentialsAuth(
            server_metadata=server_metadata, client_id="m2m", client_secret="secret123", scope="openid mcp:read"
        )

        assert auth.scope == "openid mcp:read"


# =============================================================================
# Factory Method Tests
# =============================================================================


class TestClientCredentialsAuthFromResource:
    """Tests for ClientCredentialsAuth.from_resource factory method."""

    @respx.mock
    @pytest.mark.anyio
    async def test_from_resource_full_discovery(self):
        """from_resource performs full discovery and returns configured auth."""
        from dedalus_mcp.client.auth.client_credentials import ClientCredentialsAuth

        # Mock initial 401 response
        respx.get("https://mcp.example.com/mcp").mock(
            return_value=httpx.Response(
                401, headers={"WWW-Authenticate": 'Bearer resource_metadata="/.well-known/oauth-protected-resource"'}
            )
        )

        # Mock PRM endpoint
        respx.get("https://mcp.example.com/.well-known/oauth-protected-resource").mock(
            return_value=httpx.Response(
                200, json={"resource": "https://mcp.example.com", "authorization_servers": ["https://as.example.com"]}
            )
        )

        # Mock AS metadata endpoint
        respx.get("https://as.example.com/.well-known/oauth-authorization-server").mock(
            return_value=httpx.Response(
                200,
                json={
                    "issuer": "https://as.example.com",
                    "token_endpoint": "https://as.example.com/oauth2/token",
                    "grant_types_supported": ["client_credentials"],
                },
            )
        )

        auth = await ClientCredentialsAuth.from_resource(
            resource_url="https://mcp.example.com/mcp", client_id="m2m", client_secret="secret123"
        )

        assert auth.client_id == "m2m"
        assert auth.token_endpoint == "https://as.example.com/oauth2/token"

    @respx.mock
    @pytest.mark.anyio
    async def test_from_resource_unprotected_raises(self):
        """from_resource raises if resource is not protected (no 401)."""
        from dedalus_mcp.client.auth.client_credentials import ClientCredentialsAuth
        from dedalus_mcp.client.auth.discovery import DiscoveryError

        respx.get("https://mcp.example.com/mcp").mock(return_value=httpx.Response(200))

        with pytest.raises(DiscoveryError, match="not protected"):
            await ClientCredentialsAuth.from_resource(
                resource_url="https://mcp.example.com/mcp", client_id="m2m", client_secret="secret123"
            )


# =============================================================================
# Token Acquisition Tests
# =============================================================================


class TestClientCredentialsAuthTokenAcquisition:
    """Tests for token acquisition via client credentials grant."""

    @respx.mock
    @pytest.mark.anyio
    async def test_get_token_success(self):
        """get_token acquires token from token endpoint."""
        from dedalus_mcp.client.auth.client_credentials import ClientCredentialsAuth
        from dedalus_mcp.client.auth.models import AuthorizationServerMetadata

        server_metadata = AuthorizationServerMetadata(
            issuer="https://as.example.com",
            token_endpoint="https://as.example.com/oauth2/token",
            grant_types_supported=["client_credentials"],
        )

        respx.post("https://as.example.com/oauth2/token").mock(
            return_value=httpx.Response(
                200, json={"access_token": "eyJhbGciOiJFUzI1NiIs...", "token_type": "Bearer", "expires_in": 3600}
            )
        )

        auth = ClientCredentialsAuth(server_metadata=server_metadata, client_id="m2m", client_secret="secret123")

        token = await auth.get_token()

        assert token.access_token == "eyJhbGciOiJFUzI1NiIs..."
        assert token.token_type == "Bearer"
        assert token.expires_in == 3600

    @respx.mock
    @pytest.mark.anyio
    async def test_get_token_with_scope(self):
        """get_token sends scope in token request."""
        from dedalus_mcp.client.auth.client_credentials import ClientCredentialsAuth
        from dedalus_mcp.client.auth.models import AuthorizationServerMetadata

        server_metadata = AuthorizationServerMetadata(
            issuer="https://as.example.com",
            token_endpoint="https://as.example.com/oauth2/token",
            grant_types_supported=["client_credentials"],
        )

        route = respx.post("https://as.example.com/oauth2/token").mock(
            return_value=httpx.Response(200, json={"access_token": "token", "token_type": "Bearer"})
        )

        auth = ClientCredentialsAuth(
            server_metadata=server_metadata, client_id="m2m", client_secret="secret123", scope="openid mcp:read"
        )

        await auth.get_token()

        # Verify scope was sent in request
        request = route.calls.last.request
        body = request.content.decode()
        assert "scope=openid" in body or "scope=openid+mcp%3Aread" in body or "openid" in body

    @respx.mock
    @pytest.mark.anyio
    async def test_get_token_uses_basic_auth(self):
        """get_token uses HTTP Basic Auth for client authentication."""
        from dedalus_mcp.client.auth.client_credentials import ClientCredentialsAuth
        from dedalus_mcp.client.auth.models import AuthorizationServerMetadata
        import base64

        server_metadata = AuthorizationServerMetadata(
            issuer="https://as.example.com",
            token_endpoint="https://as.example.com/oauth2/token",
            grant_types_supported=["client_credentials"],
        )

        route = respx.post("https://as.example.com/oauth2/token").mock(
            return_value=httpx.Response(200, json={"access_token": "token", "token_type": "Bearer"})
        )

        auth = ClientCredentialsAuth(server_metadata=server_metadata, client_id="m2m", client_secret="secret123")

        await auth.get_token()

        # Verify Basic Auth header
        request = route.calls.last.request
        auth_header = request.headers.get("Authorization")
        assert auth_header is not None
        assert auth_header.startswith("Basic ")

        # Decode and verify credentials
        encoded = auth_header.split(" ")[1]
        decoded = base64.b64decode(encoded).decode()
        assert decoded == "m2m:secret123"

    @respx.mock
    @pytest.mark.anyio
    async def test_get_token_error_response(self):
        """get_token raises on error response from token endpoint."""
        from dedalus_mcp.client.auth.client_credentials import ClientCredentialsAuth, TokenError
        from dedalus_mcp.client.auth.models import AuthorizationServerMetadata

        server_metadata = AuthorizationServerMetadata(
            issuer="https://as.example.com",
            token_endpoint="https://as.example.com/oauth2/token",
            grant_types_supported=["client_credentials"],
        )

        respx.post("https://as.example.com/oauth2/token").mock(
            return_value=httpx.Response(
                400, json={"error": "invalid_client", "error_description": "Client authentication failed"}
            )
        )

        auth = ClientCredentialsAuth(server_metadata=server_metadata, client_id="m2m", client_secret="wrong_secret")

        with pytest.raises(TokenError, match="invalid_client"):
            await auth.get_token()


# =============================================================================
# httpx.Auth Interface Tests
# =============================================================================


class TestClientCredentialsAuthHttpxInterface:
    """Tests for ClientCredentialsAuth as httpx.Auth implementation."""

    @respx.mock
    @pytest.mark.anyio
    async def test_auth_flow_injects_bearer_token(self):
        """ClientCredentialsAuth injects Bearer token into requests."""
        from dedalus_mcp.client.auth.client_credentials import ClientCredentialsAuth
        from dedalus_mcp.client.auth.models import AuthorizationServerMetadata

        server_metadata = AuthorizationServerMetadata(
            issuer="https://as.example.com",
            token_endpoint="https://as.example.com/oauth2/token",
            grant_types_supported=["client_credentials"],
        )

        # Mock token endpoint
        respx.post("https://as.example.com/oauth2/token").mock(
            return_value=httpx.Response(
                200, json={"access_token": "the_access_token", "token_type": "Bearer", "expires_in": 3600}
            )
        )

        # Mock protected resource
        protected_route = respx.get("https://mcp.example.com/api").mock(
            return_value=httpx.Response(200, json={"result": "success"})
        )

        auth = ClientCredentialsAuth(server_metadata=server_metadata, client_id="m2m", client_secret="secret123")

        # Pre-fetch token
        await auth.get_token()

        # Make request with auth
        async with httpx.AsyncClient() as client:
            response = await client.get("https://mcp.example.com/api", auth=auth)

        assert response.status_code == 200

        # Verify Bearer token was injected
        request = protected_route.calls.last.request
        assert request.headers.get("Authorization") == "Bearer the_access_token"

    @respx.mock
    @pytest.mark.anyio
    async def test_token_caching(self):
        """ClientCredentialsAuth caches token and reuses it."""
        from dedalus_mcp.client.auth.client_credentials import ClientCredentialsAuth
        from dedalus_mcp.client.auth.models import AuthorizationServerMetadata

        server_metadata = AuthorizationServerMetadata(
            issuer="https://as.example.com",
            token_endpoint="https://as.example.com/oauth2/token",
            grant_types_supported=["client_credentials"],
        )

        token_route = respx.post("https://as.example.com/oauth2/token").mock(
            return_value=httpx.Response(
                200, json={"access_token": "cached_token", "token_type": "Bearer", "expires_in": 3600}
            )
        )

        auth = ClientCredentialsAuth(server_metadata=server_metadata, client_id="m2m", client_secret="secret123")

        # Get token twice
        token1 = await auth.get_token()
        token2 = await auth.get_token()

        # Should only hit token endpoint once
        assert len(token_route.calls) == 1
        assert token1.access_token == token2.access_token


# =============================================================================
# Resource Indicator Tests (RFC 8707)
# =============================================================================


class TestClientCredentialsAuthResourceIndicator:
    """Tests for resource indicator support (RFC 8707)."""

    @respx.mock
    @pytest.mark.anyio
    async def test_get_token_with_resource_indicator(self):
        """get_token can include resource indicator in token request."""
        from dedalus_mcp.client.auth.client_credentials import ClientCredentialsAuth
        from dedalus_mcp.client.auth.models import AuthorizationServerMetadata

        server_metadata = AuthorizationServerMetadata(
            issuer="https://as.example.com",
            token_endpoint="https://as.example.com/oauth2/token",
            grant_types_supported=["client_credentials"],
        )

        route = respx.post("https://as.example.com/oauth2/token").mock(
            return_value=httpx.Response(200, json={"access_token": "token", "token_type": "Bearer"})
        )

        auth = ClientCredentialsAuth(
            server_metadata=server_metadata,
            client_id="m2m",
            client_secret="secret123",
            resource="https://mcp.example.com",
        )

        await auth.get_token()

        # Verify resource was sent in request
        request = route.calls.last.request
        body = request.content.decode()
        assert "resource=" in body
