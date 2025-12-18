# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""OAuth metadata models (RFC 9728, RFC 8414).

This module defines data models for:
- Protected Resource Metadata (RFC 9728)
- Authorization Server Metadata (RFC 8414)
- Token responses
- WWW-Authenticate header parsing
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class ResourceMetadata:
    """OAuth 2.0 Protected Resource Metadata (RFC 9728).

    Describes the OAuth configuration of a protected resource,
    including which authorization servers can issue tokens for it.
    """

    resource: str
    authorization_servers: list[str]
    scopes_supported: list[str] | None = None
    bearer_methods_supported: list[str] | None = None
    resource_signing_alg_values_supported: list[str] | None = None

    @property
    def primary_authorization_server(self) -> str:
        """Return the first (primary) authorization server."""
        return self.authorization_servers[0]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ResourceMetadata:
        """Create ResourceMetadata from a dictionary.

        Raises:
            ValueError: If required fields are missing.
        """
        if "resource" not in data:
            raise ValueError("Missing required field: resource")
        if "authorization_servers" not in data:
            raise ValueError("Missing required field: authorization_servers")

        return cls(
            resource=data["resource"],
            authorization_servers=data["authorization_servers"],
            scopes_supported=data.get("scopes_supported"),
            bearer_methods_supported=data.get("bearer_methods_supported"),
            resource_signing_alg_values_supported=data.get("resource_signing_alg_values_supported"),
        )


@dataclass
class AuthorizationServerMetadata:
    """OAuth 2.0 Authorization Server Metadata (RFC 8414).

    Describes the OAuth configuration of an authorization server,
    including endpoints and supported features.
    """

    issuer: str
    token_endpoint: str
    authorization_endpoint: str | None = None
    registration_endpoint: str | None = None
    jwks_uri: str | None = None
    scopes_supported: list[str] | None = None
    response_types_supported: list[str] | None = None
    grant_types_supported: list[str] | None = None
    token_endpoint_auth_methods_supported: list[str] | None = None
    code_challenge_methods_supported: list[str] | None = None

    def supports_grant_type(self, grant_type: str) -> bool:
        """Check if the AS supports a specific grant type."""
        if self.grant_types_supported is None:
            return False
        return grant_type in self.grant_types_supported

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AuthorizationServerMetadata:
        """Create AuthorizationServerMetadata from a dictionary.

        Raises:
            ValueError: If required fields are missing.
        """
        if "issuer" not in data:
            raise ValueError("Missing required field: issuer")
        if "token_endpoint" not in data:
            raise ValueError("Missing required field: token_endpoint")

        return cls(
            issuer=data["issuer"],
            token_endpoint=data["token_endpoint"],
            authorization_endpoint=data.get("authorization_endpoint"),
            registration_endpoint=data.get("registration_endpoint"),
            jwks_uri=data.get("jwks_uri"),
            scopes_supported=data.get("scopes_supported"),
            response_types_supported=data.get("response_types_supported"),
            grant_types_supported=data.get("grant_types_supported"),
            token_endpoint_auth_methods_supported=data.get("token_endpoint_auth_methods_supported"),
            code_challenge_methods_supported=data.get("code_challenge_methods_supported"),
        )


@dataclass
class TokenResponse:
    """OAuth token response.

    Contains the access token and related metadata returned
    from the token endpoint.
    """

    access_token: str
    token_type: str
    expires_in: int | None = None
    refresh_token: str | None = None
    scope: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TokenResponse:
        """Create TokenResponse from a dictionary.

        Raises:
            ValueError: If required fields are missing.
        """
        if "access_token" not in data:
            raise ValueError("Missing required field: access_token")
        if "token_type" not in data:
            raise ValueError("Missing required field: token_type")

        return cls(
            access_token=data["access_token"],
            token_type=data["token_type"],
            expires_in=data.get("expires_in"),
            refresh_token=data.get("refresh_token"),
            scope=data.get("scope"),
        )


@dataclass
class WWWAuthenticateChallenge:
    """Parsed WWW-Authenticate header challenge."""

    scheme: str
    error: str | None = None
    error_description: str | None = None
    resource_metadata: str | None = None


# Regex to parse WWW-Authenticate parameters
_PARAM_PATTERN = re.compile(r'(\w+)="([^"]*)"')


def parse_www_authenticate(header: str) -> WWWAuthenticateChallenge:
    """Parse a WWW-Authenticate header value.

    Args:
        header: The WWW-Authenticate header value.

    Returns:
        Parsed challenge with scheme and parameters.

    Raises:
        ValueError: If the header is empty or malformed.
    """
    if not header:
        raise ValueError("Empty WWW-Authenticate header")

    parts = header.split(None, 1)
    if not parts:
        raise ValueError("Malformed WWW-Authenticate header")

    scheme = parts[0]
    params_str = parts[1] if len(parts) > 1 else ""

    # Validate scheme looks reasonable
    if not scheme.isalpha():
        raise ValueError("Malformed WWW-Authenticate header: invalid scheme")

    # Parse parameters
    params: dict[str, str] = {}
    for match in _PARAM_PATTERN.finditer(params_str):
        params[match.group(1)] = match.group(2)

    return WWWAuthenticateChallenge(
        scheme=scheme,
        error=params.get("error"),
        error_description=params.get("error_description"),
        resource_metadata=params.get("resource_metadata"),
    )
