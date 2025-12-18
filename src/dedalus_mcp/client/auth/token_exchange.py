# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""OAuth 2.0 Token Exchange Auth (RFC 8693).

TokenExchangeAuth exchanges an existing token (e.g., from Clerk, Auth0)
for an MCP-scoped access token. Used for user delegation flows.
"""

from __future__ import annotations

from typing import Generator

import httpx

from .discovery import discover_authorization_server
from .models import AuthorizationServerMetadata, TokenResponse

# RFC 8693 grant type
TOKEN_EXCHANGE_GRANT = "urn:ietf:params:oauth:grant-type:token-exchange"

# RFC 8693 token types
ACCESS_TOKEN_TYPE = "urn:ietf:params:oauth:token-type:access_token"
ID_TOKEN_TYPE = "urn:ietf:params:oauth:token-type:id_token"


class AuthConfigError(Exception):
    """Configuration error for authentication."""


class TokenError(Exception):
    """Error acquiring token."""


class TokenExchangeAuth(httpx.Auth):
    """OAuth 2.0 Token Exchange authentication (RFC 8693).

    Implements httpx.Auth for transparent token injection into HTTP requests.
    Exchanges an existing token for a new access token.
    """

    def __init__(
        self,
        *,
        server_metadata: AuthorizationServerMetadata,
        client_id: str,
        subject_token: str,
        subject_token_type: str = ACCESS_TOKEN_TYPE,
        actor_token: str | None = None,
        actor_token_type: str | None = None,
        scope: str | None = None,
        resource: str | None = None,
    ) -> None:
        """Initialize TokenExchangeAuth.

        Args:
            server_metadata: Authorization Server metadata.
            client_id: OAuth client ID.
            subject_token: The token to exchange.
            subject_token_type: Type of subject token (default: access_token).
            actor_token: Optional actor token for delegation.
            actor_token_type: Type of actor token.
            scope: Optional scope to request.
            resource: Optional resource indicator (RFC 8707).

        Raises:
            AuthConfigError: If AS doesn't support token-exchange grant.
        """
        if not server_metadata.supports_grant_type(TOKEN_EXCHANGE_GRANT):
            raise AuthConfigError(
                "Authorization server does not support token-exchange grant type"
            )

        self._server_metadata = server_metadata
        self._client_id = client_id
        self._subject_token = subject_token
        self._subject_token_type = subject_token_type
        self._actor_token = actor_token
        self._actor_token_type = actor_token_type or ACCESS_TOKEN_TYPE
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
    def subject_token_type(self) -> str:
        """Return the subject token type."""
        return self._subject_token_type

    @property
    def actor_token(self) -> str | None:
        """Return the actor token."""
        return self._actor_token

    @classmethod
    async def from_resource(
        cls,
        *,
        resource_url: str,
        client_id: str,
        subject_token: str,
        subject_token_type: str = ACCESS_TOKEN_TYPE,
        scope: str | None = None,
    ) -> TokenExchangeAuth:
        """Create TokenExchangeAuth via OAuth discovery.

        Performs the full discovery flow:
        1. Probes resource for 401
        2. Fetches Protected Resource Metadata
        3. Fetches Authorization Server Metadata
        4. Returns configured auth instance

        Args:
            resource_url: URL of the protected resource.
            client_id: OAuth client ID.
            subject_token: The token to exchange.
            subject_token_type: Type of subject token.
            scope: Optional scope to request.

        Returns:
            Configured TokenExchangeAuth instance.

        Raises:
            DiscoveryError: If discovery fails.
            AuthConfigError: If AS doesn't support token-exchange.
        """
        async with httpx.AsyncClient() as client:
            result = await discover_authorization_server(client, resource_url)

        return cls(
            server_metadata=result.authorization_server_metadata,
            client_id=client_id,
            subject_token=subject_token,
            subject_token_type=subject_token_type,
            scope=scope,
            resource=result.resource_metadata.resource,
        )

    async def get_token(self) -> TokenResponse:
        """Exchange subject token for an access token.

        Caches the token for reuse.

        Returns:
            TokenResponse with access token.

        Raises:
            TokenError: If token exchange fails.
        """
        if self._cached_token is not None:
            return self._cached_token

        data = {
            "grant_type": TOKEN_EXCHANGE_GRANT,
            "client_id": self._client_id,
            "subject_token": self._subject_token,
            "subject_token_type": self._subject_token_type,
        }

        if self._actor_token:
            data["actor_token"] = self._actor_token
            data["actor_token_type"] = self._actor_token_type

        if self._scope:
            data["scope"] = self._scope
        if self._resource:
            data["resource"] = self._resource

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self._server_metadata.token_endpoint,
                data=data,
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
                raise TokenError(f"Token exchange failed: {response.status_code}")

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
