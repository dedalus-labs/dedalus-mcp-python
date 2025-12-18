# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""OAuth 2.0 Client Credentials Auth (RFC 6749 Section 4.4).

ClientCredentialsAuth is the primary auth mechanism for M2M (machine-to-machine)
communication, CI/CD pipelines, and backend services.
"""

from __future__ import annotations

from typing import Generator

import httpx

from .discovery import discover_authorization_server
from .models import AuthorizationServerMetadata, TokenResponse


class AuthConfigError(Exception):
    """Configuration error for authentication."""


class TokenError(Exception):
    """Error acquiring token."""


class ClientCredentialsAuth(httpx.Auth):
    """OAuth 2.0 Client Credentials authentication.

    Implements httpx.Auth for transparent token injection into HTTP requests.
    Acquires tokens using the client_credentials grant type.
    """

    def __init__(
        self,
        *,
        server_metadata: AuthorizationServerMetadata,
        client_id: str,
        client_secret: str,
        scope: str | None = None,
        resource: str | None = None,
    ) -> None:
        """Initialize ClientCredentialsAuth.

        Args:
            server_metadata: Authorization Server metadata.
            client_id: OAuth client ID.
            client_secret: OAuth client secret.
            scope: Optional scope to request.
            resource: Optional resource indicator (RFC 8707).

        Raises:
            AuthConfigError: If AS doesn't support client_credentials grant.
        """
        if not server_metadata.supports_grant_type("client_credentials"):
            raise AuthConfigError(
                "Authorization server does not support client_credentials grant type"
            )

        self._server_metadata = server_metadata
        self._client_id = client_id
        self._client_secret = client_secret
        self._scope = scope
        self._resource = resource
        self._cached_token: TokenResponse | None = None

    @property
    def client_id(self) -> str:
        """Return the client ID."""
        return self._client_id

    @property
    def token_endpoint(self) -> str:
        """Return the token endpoint URL."""
        return self._server_metadata.token_endpoint

    @property
    def scope(self) -> str | None:
        """Return the configured scope."""
        return self._scope

    @classmethod
    async def from_resource(
        cls,
        *,
        resource_url: str,
        client_id: str,
        client_secret: str,
        scope: str | None = None,
    ) -> ClientCredentialsAuth:
        """Create ClientCredentialsAuth via OAuth discovery.

        Performs the full discovery flow:
        1. Probes resource for 401
        2. Fetches Protected Resource Metadata
        3. Fetches Authorization Server Metadata
        4. Returns configured auth instance

        Args:
            resource_url: URL of the protected resource.
            client_id: OAuth client ID.
            client_secret: OAuth client secret.
            scope: Optional scope to request.

        Returns:
            Configured ClientCredentialsAuth instance.

        Raises:
            DiscoveryError: If discovery fails.
            AuthConfigError: If AS doesn't support client_credentials.
        """
        async with httpx.AsyncClient() as client:
            result = await discover_authorization_server(client, resource_url)

        return cls(
            server_metadata=result.authorization_server_metadata,
            client_id=client_id,
            client_secret=client_secret,
            scope=scope,
            resource=result.resource_metadata.resource,
        )

    async def get_token(self) -> TokenResponse:
        """Acquire an access token using client credentials.

        Caches the token for reuse.

        Returns:
            TokenResponse with access token.

        Raises:
            TokenError: If token acquisition fails.
        """
        if self._cached_token is not None:
            return self._cached_token

        data = {
            "grant_type": "client_credentials",
        }
        if self._scope:
            data["scope"] = self._scope
        if self._resource:
            data["resource"] = self._resource

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self._server_metadata.token_endpoint,
                data=data,
                auth=(self._client_id, self._client_secret),
            )

        if response.status_code != 200:
            try:
                error_data = response.json()
                error = error_data.get("error", "unknown_error")
                description = error_data.get("error_description", "")
                raise TokenError(f"{error}: {description}")
            except TokenError:
                raise
            except Exception:
                raise TokenError(f"Token request failed: {response.status_code}")

        token = TokenResponse.from_dict(response.json())
        self._cached_token = token
        return token

    def sync_auth_flow(
        self, request: httpx.Request
    ) -> Generator[httpx.Request, httpx.Response, None]:
        """Synchronous auth flow for httpx.Auth interface.

        Injects the Bearer token into the request. Token must be
        pre-fetched via get_token() for sync usage.
        """
        if self._cached_token is not None:
            request.headers["Authorization"] = f"Bearer {self._cached_token.access_token}"
        yield request

    async def async_auth_flow(
        self, request: httpx.Request
    ) -> Generator[httpx.Request, httpx.Response, None]:
        """Async auth flow for httpx.Auth interface.

        Injects the Bearer token into the request. Token must be
        pre-fetched via get_token() for proper operation.
        """
        if self._cached_token is not None:
            request.headers["Authorization"] = f"Bearer {self._cached_token.access_token}"
        yield request
