# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Tests for OAuth 2.0 Token Exchange Auth (RFC 8693).

TokenExchangeAuth exchanges an existing token (e.g., from Clerk, Auth0)
for an MCP-scoped access token. Used for user delegation flows.
"""

from __future__ import annotations

import httpx
import pytest
import respx


# =============================================================================
# TokenExchangeAuth Construction Tests
# =============================================================================


class TestTokenExchangeAuthConstruction:
    """Tests for TokenExchangeAuth initialization."""

    def test_construction_with_server_metadata(self):
        """TokenExchangeAuth can be constructed with AS metadata."""
        from dedalus_mcp.client.auth.models import AuthorizationServerMetadata
        from dedalus_mcp.client.auth.token_exchange import TokenExchangeAuth

        server_metadata = AuthorizationServerMetadata(
            issuer="https://as.example.com",
            token_endpoint="https://as.example.com/oauth2/token",
            grant_types_supported=["urn:ietf:params:oauth:grant-type:token-exchange"],
        )

        auth = TokenExchangeAuth(
            server_metadata=server_metadata, client_id="dedalus-sdk", subject_token="eyJhbGciOiJSUzI1NiIs..."
        )

        assert auth.client_id == "dedalus-sdk"
        assert auth.token_endpoint == "https://as.example.com/oauth2/token"

    def test_construction_validates_grant_type_support(self):
        """TokenExchangeAuth raises if AS doesn't support token-exchange."""
        from dedalus_mcp.client.auth.models import AuthorizationServerMetadata
        from dedalus_mcp.client.auth.token_exchange import AuthConfigError, TokenExchangeAuth

        server_metadata = AuthorizationServerMetadata(
            issuer="https://as.example.com",
            token_endpoint="https://as.example.com/oauth2/token",
            grant_types_supported=["client_credentials"],  # No token-exchange
        )

        with pytest.raises(AuthConfigError, match="token-exchange"):
            TokenExchangeAuth(server_metadata=server_metadata, client_id="dedalus-sdk", subject_token="token")

    def test_construction_with_subject_token_type(self):
        """TokenExchangeAuth accepts subject_token_type parameter."""
        from dedalus_mcp.client.auth.models import AuthorizationServerMetadata
        from dedalus_mcp.client.auth.token_exchange import TokenExchangeAuth

        server_metadata = AuthorizationServerMetadata(
            issuer="https://as.example.com",
            token_endpoint="https://as.example.com/oauth2/token",
            grant_types_supported=["urn:ietf:params:oauth:grant-type:token-exchange"],
        )

        auth = TokenExchangeAuth(
            server_metadata=server_metadata,
            client_id="dedalus-sdk",
            subject_token="token",
            subject_token_type="urn:ietf:params:oauth:token-type:id_token",
        )

        assert auth.subject_token_type == "urn:ietf:params:oauth:token-type:id_token"

    def test_construction_default_subject_token_type(self):
        """TokenExchangeAuth defaults to access_token type."""
        from dedalus_mcp.client.auth.models import AuthorizationServerMetadata
        from dedalus_mcp.client.auth.token_exchange import TokenExchangeAuth

        server_metadata = AuthorizationServerMetadata(
            issuer="https://as.example.com",
            token_endpoint="https://as.example.com/oauth2/token",
            grant_types_supported=["urn:ietf:params:oauth:grant-type:token-exchange"],
        )

        auth = TokenExchangeAuth(server_metadata=server_metadata, client_id="dedalus-sdk", subject_token="token")

        assert auth.subject_token_type == "urn:ietf:params:oauth:token-type:access_token"


# =============================================================================
# Factory Method Tests
# =============================================================================


class TestTokenExchangeAuthFromResource:
    """Tests for TokenExchangeAuth.from_resource factory method."""

    @respx.mock
    @pytest.mark.anyio
    async def test_from_resource_full_discovery(self):
        """from_resource performs full discovery and returns configured auth."""
        from dedalus_mcp.client.auth.token_exchange import TokenExchangeAuth

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
                    "grant_types_supported": ["urn:ietf:params:oauth:grant-type:token-exchange"],
                },
            )
        )

        auth = await TokenExchangeAuth.from_resource(
            resource_url="https://mcp.example.com/mcp", client_id="dedalus-sdk", subject_token="user_token_from_clerk"
        )

        assert auth.client_id == "dedalus-sdk"
        assert auth.token_endpoint == "https://as.example.com/oauth2/token"


# =============================================================================
# Token Exchange Tests
# =============================================================================


class TestTokenExchangeAuthTokenAcquisition:
    """Tests for token acquisition via token exchange grant."""

    @respx.mock
    @pytest.mark.anyio
    async def test_get_token_success(self):
        """get_token exchanges subject token for access token."""
        from dedalus_mcp.client.auth.models import AuthorizationServerMetadata
        from dedalus_mcp.client.auth.token_exchange import TokenExchangeAuth

        server_metadata = AuthorizationServerMetadata(
            issuer="https://as.example.com",
            token_endpoint="https://as.example.com/oauth2/token",
            grant_types_supported=["urn:ietf:params:oauth:grant-type:token-exchange"],
        )

        respx.post("https://as.example.com/oauth2/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "exchanged_access_token",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "issued_token_type": "urn:ietf:params:oauth:token-type:access_token",
                },
            )
        )

        auth = TokenExchangeAuth(
            server_metadata=server_metadata, client_id="dedalus-sdk", subject_token="user_id_token"
        )

        token = await auth.get_token()

        assert token.access_token == "exchanged_access_token"
        assert token.token_type == "Bearer"

    @respx.mock
    @pytest.mark.anyio
    async def test_get_token_sends_correct_params(self):
        """get_token sends RFC 8693 compliant parameters."""
        from dedalus_mcp.client.auth.models import AuthorizationServerMetadata
        from dedalus_mcp.client.auth.token_exchange import TokenExchangeAuth

        server_metadata = AuthorizationServerMetadata(
            issuer="https://as.example.com",
            token_endpoint="https://as.example.com/oauth2/token",
            grant_types_supported=["urn:ietf:params:oauth:grant-type:token-exchange"],
        )

        route = respx.post("https://as.example.com/oauth2/token").mock(
            return_value=httpx.Response(200, json={"access_token": "token", "token_type": "Bearer"})
        )

        auth = TokenExchangeAuth(
            server_metadata=server_metadata,
            client_id="dedalus-sdk",
            subject_token="the_subject_token",
            subject_token_type="urn:ietf:params:oauth:token-type:id_token",
        )

        await auth.get_token()

        # Verify RFC 8693 parameters
        request = route.calls.last.request
        body = request.content.decode()

        assert "grant_type=urn%3Aietf%3Aparams%3Aoauth%3Agrant-type%3Atoken-exchange" in body
        assert "subject_token=the_subject_token" in body
        assert "subject_token_type=urn%3Aietf%3Aparams%3Aoauth%3Atoken-type%3Aid_token" in body

    @respx.mock
    @pytest.mark.anyio
    async def test_get_token_with_resource_indicator(self):
        """get_token can include resource indicator."""
        from dedalus_mcp.client.auth.models import AuthorizationServerMetadata
        from dedalus_mcp.client.auth.token_exchange import TokenExchangeAuth

        server_metadata = AuthorizationServerMetadata(
            issuer="https://as.example.com",
            token_endpoint="https://as.example.com/oauth2/token",
            grant_types_supported=["urn:ietf:params:oauth:grant-type:token-exchange"],
        )

        route = respx.post("https://as.example.com/oauth2/token").mock(
            return_value=httpx.Response(200, json={"access_token": "token", "token_type": "Bearer"})
        )

        auth = TokenExchangeAuth(
            server_metadata=server_metadata,
            client_id="dedalus-sdk",
            subject_token="token",
            resource="https://mcp.example.com",
        )

        await auth.get_token()

        request = route.calls.last.request
        body = request.content.decode()
        assert "resource=" in body

    @respx.mock
    @pytest.mark.anyio
    async def test_get_token_with_scope(self):
        """get_token can include requested scope."""
        from dedalus_mcp.client.auth.models import AuthorizationServerMetadata
        from dedalus_mcp.client.auth.token_exchange import TokenExchangeAuth

        server_metadata = AuthorizationServerMetadata(
            issuer="https://as.example.com",
            token_endpoint="https://as.example.com/oauth2/token",
            grant_types_supported=["urn:ietf:params:oauth:grant-type:token-exchange"],
        )

        route = respx.post("https://as.example.com/oauth2/token").mock(
            return_value=httpx.Response(200, json={"access_token": "token", "token_type": "Bearer"})
        )

        auth = TokenExchangeAuth(
            server_metadata=server_metadata, client_id="dedalus-sdk", subject_token="token", scope="openid mcp:read"
        )

        await auth.get_token()

        request = route.calls.last.request
        body = request.content.decode()
        assert "scope=" in body

    @respx.mock
    @pytest.mark.anyio
    async def test_get_token_error_response(self):
        """get_token raises on error response."""
        from dedalus_mcp.client.auth.models import AuthorizationServerMetadata
        from dedalus_mcp.client.auth.token_exchange import TokenError, TokenExchangeAuth

        server_metadata = AuthorizationServerMetadata(
            issuer="https://as.example.com",
            token_endpoint="https://as.example.com/oauth2/token",
            grant_types_supported=["urn:ietf:params:oauth:grant-type:token-exchange"],
        )

        respx.post("https://as.example.com/oauth2/token").mock(
            return_value=httpx.Response(
                400, json={"error": "invalid_grant", "error_description": "Subject token is expired"}
            )
        )

        auth = TokenExchangeAuth(
            server_metadata=server_metadata, client_id="dedalus-sdk", subject_token="expired_token"
        )

        with pytest.raises(TokenError, match="invalid_grant"):
            await auth.get_token()


# =============================================================================
# httpx.Auth Interface Tests
# =============================================================================


class TestTokenExchangeAuthHttpxInterface:
    """Tests for TokenExchangeAuth as httpx.Auth implementation."""

    @respx.mock
    @pytest.mark.anyio
    async def test_auth_flow_injects_bearer_token(self):
        """TokenExchangeAuth injects Bearer token into requests."""
        from dedalus_mcp.client.auth.models import AuthorizationServerMetadata
        from dedalus_mcp.client.auth.token_exchange import TokenExchangeAuth

        server_metadata = AuthorizationServerMetadata(
            issuer="https://as.example.com",
            token_endpoint="https://as.example.com/oauth2/token",
            grant_types_supported=["urn:ietf:params:oauth:grant-type:token-exchange"],
        )

        # Mock token endpoint
        respx.post("https://as.example.com/oauth2/token").mock(
            return_value=httpx.Response(200, json={"access_token": "exchanged_token", "token_type": "Bearer"})
        )

        # Mock protected resource
        protected_route = respx.get("https://mcp.example.com/api").mock(
            return_value=httpx.Response(200, json={"result": "success"})
        )

        auth = TokenExchangeAuth(server_metadata=server_metadata, client_id="dedalus-sdk", subject_token="user_token")

        # Pre-fetch token
        await auth.get_token()

        # Make request with auth
        async with httpx.AsyncClient() as client:
            response = await client.get("https://mcp.example.com/api", auth=auth)

        assert response.status_code == 200

        # Verify Bearer token was injected
        request = protected_route.calls.last.request
        assert request.headers.get("Authorization") == "Bearer exchanged_token"


# =============================================================================
# Actor Token Tests (RFC 8693 Section 2.1)
# =============================================================================


class TestTokenExchangeAuthActorToken:
    """Tests for actor token support (delegation scenarios)."""

    def test_construction_with_actor_token(self):
        """TokenExchangeAuth accepts actor_token for delegation."""
        from dedalus_mcp.client.auth.models import AuthorizationServerMetadata
        from dedalus_mcp.client.auth.token_exchange import TokenExchangeAuth

        server_metadata = AuthorizationServerMetadata(
            issuer="https://as.example.com",
            token_endpoint="https://as.example.com/oauth2/token",
            grant_types_supported=["urn:ietf:params:oauth:grant-type:token-exchange"],
        )

        auth = TokenExchangeAuth(
            server_metadata=server_metadata,
            client_id="dedalus-sdk",
            subject_token="user_token",
            actor_token="service_token",
            actor_token_type="urn:ietf:params:oauth:token-type:access_token",
        )

        assert auth.actor_token == "service_token"

    @respx.mock
    @pytest.mark.anyio
    async def test_get_token_with_actor_token(self):
        """get_token includes actor_token in request when provided."""
        from dedalus_mcp.client.auth.models import AuthorizationServerMetadata
        from dedalus_mcp.client.auth.token_exchange import TokenExchangeAuth

        server_metadata = AuthorizationServerMetadata(
            issuer="https://as.example.com",
            token_endpoint="https://as.example.com/oauth2/token",
            grant_types_supported=["urn:ietf:params:oauth:grant-type:token-exchange"],
        )

        route = respx.post("https://as.example.com/oauth2/token").mock(
            return_value=httpx.Response(200, json={"access_token": "token", "token_type": "Bearer"})
        )

        auth = TokenExchangeAuth(
            server_metadata=server_metadata,
            client_id="dedalus-sdk",
            subject_token="user_token",
            actor_token="service_token",
        )

        await auth.get_token()

        request = route.calls.last.request
        body = request.content.decode()
        assert "actor_token=service_token" in body
