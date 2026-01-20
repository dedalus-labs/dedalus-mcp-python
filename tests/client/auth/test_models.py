# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Tests for OAuth metadata models (RFC 9728, RFC 8414)."""

from __future__ import annotations

import pytest


# =============================================================================
# ResourceMetadata Tests (RFC 9728)
# =============================================================================


class TestResourceMetadata:
    """Tests for OAuth 2.0 Protected Resource Metadata (RFC 9728)."""

    def test_construction_minimal(self):
        """ResourceMetadata can be constructed with minimal required fields."""
        from dedalus_mcp.client.auth.models import ResourceMetadata

        meta = ResourceMetadata(resource="https://mcp.example.com", authorization_servers=["https://as.example.com"])
        assert meta.resource == "https://mcp.example.com"
        assert meta.authorization_servers == ["https://as.example.com"]

    def test_construction_full(self):
        """ResourceMetadata can be constructed with all optional fields."""
        from dedalus_mcp.client.auth.models import ResourceMetadata

        meta = ResourceMetadata(
            resource="https://mcp.example.com",
            authorization_servers=["https://as.example.com", "https://as2.example.com"],
            scopes_supported=["openid", "read", "write"],
            bearer_methods_supported=["header"],
            resource_signing_alg_values_supported=["RS256", "ES256"],
        )
        assert meta.resource == "https://mcp.example.com"
        assert len(meta.authorization_servers) == 2
        assert meta.scopes_supported == ["openid", "read", "write"]
        assert meta.bearer_methods_supported == ["header"]
        assert meta.resource_signing_alg_values_supported == ["RS256", "ES256"]

    def test_from_dict(self):
        """ResourceMetadata can be created from a dictionary."""
        from dedalus_mcp.client.auth.models import ResourceMetadata

        data = {
            "resource": "https://mcp.example.com",
            "authorization_servers": ["https://as.example.com"],
            "scopes_supported": ["openid"],
        }
        meta = ResourceMetadata.from_dict(data)
        assert meta.resource == "https://mcp.example.com"
        assert meta.authorization_servers == ["https://as.example.com"]
        assert meta.scopes_supported == ["openid"]

    def test_from_dict_ignores_unknown_fields(self):
        """ResourceMetadata.from_dict ignores unknown fields."""
        from dedalus_mcp.client.auth.models import ResourceMetadata

        data = {
            "resource": "https://mcp.example.com",
            "authorization_servers": ["https://as.example.com"],
            "unknown_field": "should be ignored",
        }
        meta = ResourceMetadata.from_dict(data)
        assert meta.resource == "https://mcp.example.com"
        assert not hasattr(meta, "unknown_field")

    def test_from_dict_missing_required_field_raises(self):
        """ResourceMetadata.from_dict raises on missing required fields."""
        from dedalus_mcp.client.auth.models import ResourceMetadata

        with pytest.raises(ValueError, match="resource"):
            ResourceMetadata.from_dict({"authorization_servers": ["https://as.example.com"]})

        with pytest.raises(ValueError, match="authorization_servers"):
            ResourceMetadata.from_dict({"resource": "https://mcp.example.com"})

    def test_primary_authorization_server(self):
        """primary_authorization_server returns first AS."""
        from dedalus_mcp.client.auth.models import ResourceMetadata

        meta = ResourceMetadata(
            resource="https://mcp.example.com",
            authorization_servers=["https://as1.example.com", "https://as2.example.com"],
        )
        assert meta.primary_authorization_server == "https://as1.example.com"


# =============================================================================
# AuthorizationServerMetadata Tests (RFC 8414)
# =============================================================================


class TestAuthorizationServerMetadata:
    """Tests for OAuth 2.0 Authorization Server Metadata (RFC 8414)."""

    def test_construction_minimal(self):
        """ASMetadata can be constructed with minimal required fields."""
        from dedalus_mcp.client.auth.models import AuthorizationServerMetadata

        meta = AuthorizationServerMetadata(
            issuer="https://as.example.com", token_endpoint="https://as.example.com/oauth2/token"
        )
        assert meta.issuer == "https://as.example.com"
        assert meta.token_endpoint == "https://as.example.com/oauth2/token"

    def test_construction_full(self):
        """ASMetadata can be constructed with all common fields."""
        from dedalus_mcp.client.auth.models import AuthorizationServerMetadata

        meta = AuthorizationServerMetadata(
            issuer="https://as.example.com",
            authorization_endpoint="https://as.example.com/oauth2/auth",
            token_endpoint="https://as.example.com/oauth2/token",
            registration_endpoint="https://as.example.com/register",
            jwks_uri="https://as.example.com/.well-known/jwks.json",
            scopes_supported=["openid", "offline_access"],
            response_types_supported=["code"],
            grant_types_supported=["authorization_code", "client_credentials", "refresh_token"],
            token_endpoint_auth_methods_supported=["client_secret_basic", "client_secret_post"],
            code_challenge_methods_supported=["S256"],
        )
        assert meta.issuer == "https://as.example.com"
        assert meta.authorization_endpoint == "https://as.example.com/oauth2/auth"
        assert "client_credentials" in meta.grant_types_supported
        assert "S256" in meta.code_challenge_methods_supported

    def test_from_dict(self):
        """ASMetadata can be created from a dictionary."""
        from dedalus_mcp.client.auth.models import AuthorizationServerMetadata

        data = {
            "issuer": "https://as.example.com",
            "token_endpoint": "https://as.example.com/oauth2/token",
            "grant_types_supported": ["client_credentials"],
        }
        meta = AuthorizationServerMetadata.from_dict(data)
        assert meta.issuer == "https://as.example.com"
        assert meta.token_endpoint == "https://as.example.com/oauth2/token"
        assert meta.grant_types_supported == ["client_credentials"]

    def test_from_dict_ignores_unknown_fields(self):
        """ASMetadata.from_dict ignores unknown fields."""
        from dedalus_mcp.client.auth.models import AuthorizationServerMetadata

        data = {
            "issuer": "https://as.example.com",
            "token_endpoint": "https://as.example.com/oauth2/token",
            "custom_extension": "value",
        }
        meta = AuthorizationServerMetadata.from_dict(data)
        assert meta.issuer == "https://as.example.com"
        assert not hasattr(meta, "custom_extension")

    def test_from_dict_missing_required_field_raises(self):
        """ASMetadata.from_dict raises on missing required fields."""
        from dedalus_mcp.client.auth.models import AuthorizationServerMetadata

        with pytest.raises(ValueError, match="issuer"):
            AuthorizationServerMetadata.from_dict({"token_endpoint": "https://as.example.com/token"})

        with pytest.raises(ValueError, match="token_endpoint"):
            AuthorizationServerMetadata.from_dict({"issuer": "https://as.example.com"})

    def test_supports_grant_type(self):
        """supports_grant_type checks grant_types_supported list."""
        from dedalus_mcp.client.auth.models import AuthorizationServerMetadata

        meta = AuthorizationServerMetadata(
            issuer="https://as.example.com",
            token_endpoint="https://as.example.com/oauth2/token",
            grant_types_supported=["authorization_code", "client_credentials"],
        )
        assert meta.supports_grant_type("client_credentials") is True
        assert meta.supports_grant_type("authorization_code") is True
        assert meta.supports_grant_type("refresh_token") is False

    def test_supports_grant_type_default_none(self):
        """supports_grant_type returns False when grant_types_supported is None."""
        from dedalus_mcp.client.auth.models import AuthorizationServerMetadata

        meta = AuthorizationServerMetadata(
            issuer="https://as.example.com", token_endpoint="https://as.example.com/oauth2/token"
        )
        # Per RFC 8414, if not present, default is ["authorization_code", "implicit"]
        # but we don't assume - just return False for safety
        assert meta.supports_grant_type("client_credentials") is False


# =============================================================================
# TokenResponse Tests
# =============================================================================


class TestTokenResponse:
    """Tests for OAuth token response model."""

    def test_construction(self):
        """TokenResponse can be constructed with all fields."""
        from dedalus_mcp.client.auth.models import TokenResponse

        token = TokenResponse(
            access_token="eyJhbGciOiJFUzI1NiIs...",
            token_type="Bearer",
            expires_in=3600,
            refresh_token="refresh_token_value",
            scope="openid read",
        )
        assert token.access_token == "eyJhbGciOiJFUzI1NiIs..."
        assert token.token_type == "Bearer"
        assert token.expires_in == 3600
        assert token.refresh_token == "refresh_token_value"
        assert token.scope == "openid read"

    def test_construction_minimal(self):
        """TokenResponse can be constructed with minimal fields."""
        from dedalus_mcp.client.auth.models import TokenResponse

        token = TokenResponse(access_token="eyJhbGciOiJFUzI1NiIs...", token_type="Bearer")
        assert token.access_token == "eyJhbGciOiJFUzI1NiIs..."
        assert token.token_type == "Bearer"
        assert token.expires_in is None
        assert token.refresh_token is None

    def test_from_dict(self):
        """TokenResponse can be created from a dictionary."""
        from dedalus_mcp.client.auth.models import TokenResponse

        data = {"access_token": "token123", "token_type": "Bearer", "expires_in": 7200}
        token = TokenResponse.from_dict(data)
        assert token.access_token == "token123"
        assert token.token_type == "Bearer"
        assert token.expires_in == 7200

    def test_from_dict_missing_required_raises(self):
        """TokenResponse.from_dict raises on missing required fields."""
        from dedalus_mcp.client.auth.models import TokenResponse

        with pytest.raises(ValueError, match="access_token"):
            TokenResponse.from_dict({"token_type": "Bearer"})

        with pytest.raises(ValueError, match="token_type"):
            TokenResponse.from_dict({"access_token": "token"})


# =============================================================================
# WWWAuthenticate Parsing Tests
# =============================================================================


class TestWWWAuthenticateParsing:
    """Tests for WWW-Authenticate header parsing."""

    def test_parse_bearer_with_resource_metadata(self):
        """Parse WWW-Authenticate header with resource_metadata parameter."""
        from dedalus_mcp.client.auth.models import parse_www_authenticate

        header = 'Bearer error="invalid_token", resource_metadata="/.well-known/oauth-protected-resource"'
        result = parse_www_authenticate(header)
        assert result.scheme == "Bearer"
        assert result.resource_metadata == "/.well-known/oauth-protected-resource"

    def test_parse_dpop_scheme(self):
        """Parse WWW-Authenticate header with DPoP scheme."""
        from dedalus_mcp.client.auth.models import parse_www_authenticate

        header = 'DPoP error="invalid_token", resource_metadata="/prm"'
        result = parse_www_authenticate(header)
        assert result.scheme == "DPoP"
        assert result.resource_metadata == "/prm"

    def test_parse_with_error_description(self):
        """Parse WWW-Authenticate header with error_description."""
        from dedalus_mcp.client.auth.models import parse_www_authenticate

        header = 'Bearer error="invalid_token", error_description="Token expired", resource_metadata="/prm"'
        result = parse_www_authenticate(header)
        assert result.error == "invalid_token"
        assert result.error_description == "Token expired"
        assert result.resource_metadata == "/prm"

    def test_parse_missing_resource_metadata(self):
        """parse_www_authenticate returns None for resource_metadata if not present."""
        from dedalus_mcp.client.auth.models import parse_www_authenticate

        header = 'Bearer error="invalid_token"'
        result = parse_www_authenticate(header)
        assert result.scheme == "Bearer"
        assert result.resource_metadata is None

    def test_parse_case_insensitive_scheme(self):
        """parse_www_authenticate handles case-insensitive scheme."""
        from dedalus_mcp.client.auth.models import parse_www_authenticate

        header = 'BEARER error="invalid_token", resource_metadata="/prm"'
        result = parse_www_authenticate(header)
        assert result.scheme.upper() == "BEARER"

    def test_parse_empty_raises(self):
        """parse_www_authenticate raises on empty header."""
        from dedalus_mcp.client.auth.models import parse_www_authenticate

        with pytest.raises(ValueError):
            parse_www_authenticate("")

    def test_parse_malformed_raises(self):
        """parse_www_authenticate raises on malformed header."""
        from dedalus_mcp.client.auth.models import parse_www_authenticate

        with pytest.raises(ValueError):
            parse_www_authenticate("not-a-valid-header")
