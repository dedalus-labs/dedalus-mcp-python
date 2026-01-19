# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Tests for OAuth discovery (RFC 9728, RFC 8414).

MCP clients MUST:
- Parse WWW-Authenticate headers and respond to 401 responses
- Use OAuth 2.0 Protected Resource Metadata for AS discovery
- Use OAuth 2.0 Authorization Server Metadata
"""

from __future__ import annotations

import pytest
import httpx
import respx


# =============================================================================
# Resource Metadata Discovery Tests (RFC 9728)
# =============================================================================


class TestFetchResourceMetadata:
    """Tests for fetching Protected Resource Metadata."""

    @respx.mock
    @pytest.mark.anyio
    async def test_fetch_resource_metadata_success(self):
        """fetch_resource_metadata fetches and parses PRM."""
        from dedalus_mcp.client.auth.discovery import fetch_resource_metadata

        respx.get("https://mcp.example.com/.well-known/oauth-protected-resource").mock(
            return_value=httpx.Response(
                200,
                json={
                    "resource": "https://mcp.example.com",
                    "authorization_servers": ["https://as.example.com"],
                    "scopes_supported": ["openid"],
                },
            )
        )

        async with httpx.AsyncClient() as client:
            meta = await fetch_resource_metadata(client, "https://mcp.example.com/.well-known/oauth-protected-resource")

        assert meta.resource == "https://mcp.example.com"
        assert meta.authorization_servers == ["https://as.example.com"]

    @respx.mock
    @pytest.mark.anyio
    async def test_fetch_resource_metadata_not_found(self):
        """fetch_resource_metadata raises on 404."""
        from dedalus_mcp.client.auth.discovery import fetch_resource_metadata, DiscoveryError

        respx.get("https://mcp.example.com/.well-known/oauth-protected-resource").mock(return_value=httpx.Response(404))

        async with httpx.AsyncClient() as client:
            with pytest.raises(DiscoveryError, match="404"):
                await fetch_resource_metadata(client, "https://mcp.example.com/.well-known/oauth-protected-resource")

    @respx.mock
    @pytest.mark.anyio
    async def test_fetch_resource_metadata_invalid_json(self):
        """fetch_resource_metadata raises on invalid JSON."""
        from dedalus_mcp.client.auth.discovery import fetch_resource_metadata, DiscoveryError

        respx.get("https://mcp.example.com/.well-known/oauth-protected-resource").mock(
            return_value=httpx.Response(200, content=b"not json")
        )

        async with httpx.AsyncClient() as client:
            with pytest.raises(DiscoveryError, match="JSON"):
                await fetch_resource_metadata(client, "https://mcp.example.com/.well-known/oauth-protected-resource")


# =============================================================================
# Authorization Server Metadata Discovery Tests (RFC 8414)
# =============================================================================


class TestFetchASMetadata:
    """Tests for fetching Authorization Server Metadata."""

    @respx.mock
    @pytest.mark.anyio
    async def test_fetch_authorization_server_metadata_success(self):
        """fetch_authorization_server_metadata fetches and parses AS metadata."""
        from dedalus_mcp.client.auth.discovery import fetch_authorization_server_metadata

        respx.get("https://as.example.com/.well-known/oauth-authorization-server").mock(
            return_value=httpx.Response(
                200,
                json={
                    "issuer": "https://as.example.com",
                    "token_endpoint": "https://as.example.com/oauth2/token",
                    "grant_types_supported": ["client_credentials", "authorization_code"],
                },
            )
        )

        async with httpx.AsyncClient() as client:
            meta = await fetch_authorization_server_metadata(client, "https://as.example.com")

        assert meta.issuer == "https://as.example.com"
        assert meta.token_endpoint == "https://as.example.com/oauth2/token"
        assert "client_credentials" in meta.grant_types_supported

    @respx.mock
    @pytest.mark.anyio
    async def test_fetch_authorization_server_metadata_constructs_url(self):
        """fetch_authorization_server_metadata constructs the well-known URL correctly."""
        from dedalus_mcp.client.auth.discovery import fetch_authorization_server_metadata

        # AS URL with trailing slash
        route = respx.get("https://as.example.com/.well-known/oauth-authorization-server").mock(
            return_value=httpx.Response(
                200, json={"issuer": "https://as.example.com", "token_endpoint": "https://as.example.com/oauth2/token"}
            )
        )

        async with httpx.AsyncClient() as client:
            await fetch_authorization_server_metadata(client, "https://as.example.com/")

        assert route.called

    @respx.mock
    @pytest.mark.anyio
    async def test_fetch_authorization_server_metadata_not_found(self):
        """fetch_authorization_server_metadata raises on 404."""
        from dedalus_mcp.client.auth.discovery import fetch_authorization_server_metadata, DiscoveryError

        respx.get("https://as.example.com/.well-known/oauth-authorization-server").mock(
            return_value=httpx.Response(404)
        )

        async with httpx.AsyncClient() as client:
            with pytest.raises(DiscoveryError, match="404"):
                await fetch_authorization_server_metadata(client, "https://as.example.com")


# =============================================================================
# Full Discovery Flow Tests
# =============================================================================


class TestDiscoverAuthorizationServer:
    """Tests for the complete discovery flow."""

    @respx.mock
    @pytest.mark.anyio
    async def test_discover_from_401_response(self):
        """discover_authorization_server handles 401 → PRM → AS metadata flow."""
        from dedalus_mcp.client.auth.discovery import discover_authorization_server

        # Mock 401 response with WWW-Authenticate header
        respx.get("https://mcp.example.com/mcp").mock(
            return_value=httpx.Response(
                401,
                headers={
                    "WWW-Authenticate": 'Bearer error="invalid_token", resource_metadata="/.well-known/oauth-protected-resource"'
                },
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

        async with httpx.AsyncClient() as client:
            result = await discover_authorization_server(client, "https://mcp.example.com/mcp")

        assert result.resource_metadata.resource == "https://mcp.example.com"
        assert result.authorization_server_metadata.issuer == "https://as.example.com"
        assert result.authorization_server_metadata.token_endpoint == "https://as.example.com/oauth2/token"

    @respx.mock
    @pytest.mark.anyio
    async def test_discover_no_401_raises(self):
        """discover_authorization_server raises if no 401 received."""
        from dedalus_mcp.client.auth.discovery import discover_authorization_server, DiscoveryError

        # Server returns 200 (not protected)
        respx.get("https://mcp.example.com/mcp").mock(return_value=httpx.Response(200))

        async with httpx.AsyncClient() as client:
            with pytest.raises(DiscoveryError, match="not protected"):
                await discover_authorization_server(client, "https://mcp.example.com/mcp")

    @respx.mock
    @pytest.mark.anyio
    async def test_discover_missing_www_authenticate(self):
        """discover_authorization_server raises if 401 lacks WWW-Authenticate."""
        from dedalus_mcp.client.auth.discovery import discover_authorization_server, DiscoveryError

        respx.get("https://mcp.example.com/mcp").mock(return_value=httpx.Response(401))

        async with httpx.AsyncClient() as client:
            with pytest.raises(DiscoveryError, match="WWW-Authenticate"):
                await discover_authorization_server(client, "https://mcp.example.com/mcp")

    @respx.mock
    @pytest.mark.anyio
    async def test_discover_missing_resource_metadata_param(self):
        """discover_authorization_server raises if WWW-Authenticate lacks resource_metadata."""
        from dedalus_mcp.client.auth.discovery import discover_authorization_server, DiscoveryError

        respx.get("https://mcp.example.com/mcp").mock(
            return_value=httpx.Response(401, headers={"WWW-Authenticate": 'Bearer error="invalid_token"'})
        )

        async with httpx.AsyncClient() as client:
            with pytest.raises(DiscoveryError, match="resource_metadata"):
                await discover_authorization_server(client, "https://mcp.example.com/mcp")


# =============================================================================
# URL Construction Tests
# =============================================================================


class TestBuildMetadataUrl:
    """Tests for metadata URL construction helpers."""

    def test_build_resource_metadata_url_absolute(self):
        """build_resource_metadata_url handles absolute paths."""
        from dedalus_mcp.client.auth.discovery import build_resource_metadata_url

        url = build_resource_metadata_url("https://mcp.example.com/mcp", "/.well-known/oauth-protected-resource")
        assert url == "https://mcp.example.com/.well-known/oauth-protected-resource"

    def test_build_resource_metadata_url_relative(self):
        """build_resource_metadata_url handles relative paths."""
        from dedalus_mcp.client.auth.discovery import build_resource_metadata_url

        url = build_resource_metadata_url("https://mcp.example.com/api/mcp", ".well-known/oauth-protected-resource")
        # Relative to the path
        assert "mcp.example.com" in url
        assert "oauth-protected-resource" in url

    def test_build_resource_metadata_url_full_url(self):
        """build_resource_metadata_url handles full URLs."""
        from dedalus_mcp.client.auth.discovery import build_resource_metadata_url

        url = build_resource_metadata_url("https://mcp.example.com/mcp", "https://other.example.com/.well-known/prm")
        assert url == "https://other.example.com/.well-known/prm"

    def test_build_authorization_server_metadata_url(self):
        """build_authorization_server_metadata_url constructs well-known URL."""
        from dedalus_mcp.client.auth.discovery import build_authorization_server_metadata_url

        url = build_authorization_server_metadata_url("https://as.example.com")
        assert url == "https://as.example.com/.well-known/oauth-authorization-server"

    def test_build_authorization_server_metadata_url_strips_trailing_slash(self):
        """build_authorization_server_metadata_url strips trailing slash."""
        from dedalus_mcp.client.auth.discovery import build_authorization_server_metadata_url

        url = build_authorization_server_metadata_url("https://as.example.com/")
        assert url == "https://as.example.com/.well-known/oauth-authorization-server"

    def test_build_authorization_server_metadata_url_with_path(self):
        """build_authorization_server_metadata_url handles AS URL with path."""
        from dedalus_mcp.client.auth.discovery import build_authorization_server_metadata_url

        # Per RFC 8414, if issuer has path, insert .well-known between origin and path
        url = build_authorization_server_metadata_url("https://as.example.com/tenant1")
        assert url == "https://as.example.com/.well-known/oauth-authorization-server/tenant1"
