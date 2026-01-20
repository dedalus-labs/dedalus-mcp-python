# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""OAuth authentication for MCP clients.

M2M / backend service:

    >>> auth = await ClientCredentialsAuth.from_resource(
    ...     resource_url="https://mcp.example.com/mcp",
    ...     client_id="my-service",
    ...     client_secret=os.environ["CLIENT_SECRET"],
    ... )
    >>> async with await MCPClient.connect(
    ...     "https://mcp.example.com/mcp", auth=auth
    ... ) as client:
    ...     tools = await client.list_tools()

User delegation (e.g., from Clerk token):

    >>> auth = await TokenExchangeAuth.from_resource(
    ...     resource_url="https://mcp.example.com/mcp",
    ...     client_id="my-app",
    ...     subject_token=clerk_session_token,
    ... )
    >>> async with await MCPClient.connect(
    ...     "https://mcp.example.com/mcp", auth=auth
    ... ) as client:
    ...     tools = await client.list_tools()
"""

from .authorization_code import AuthorizationCodeAuth
from .client_credentials import AuthConfigError, ClientCredentialsAuth, TokenError
from .device_code import DeviceCodeAuth
from .discovery import (
    DiscoveryError,
    DiscoveryResult,
    discover_authorization_server,
    fetch_authorization_server_metadata,
    fetch_resource_metadata,
)
from .models import (
    AuthorizationServerMetadata,
    ResourceMetadata,
    TokenResponse,
    WWWAuthenticateChallenge,
    parse_www_authenticate,
)
from .token_exchange import TokenExchangeAuth


__all__ = [
    # Primary auth classes
    "ClientCredentialsAuth",
    "TokenExchangeAuth",
    # Stubs for future
    "DeviceCodeAuth",
    "AuthorizationCodeAuth",
    # Discovery
    "discover_authorization_server",
    "fetch_authorization_server_metadata",
    "fetch_resource_metadata",
    "DiscoveryResult",
    "DiscoveryError",
    # Models
    "ResourceMetadata",
    "AuthorizationServerMetadata",
    "TokenResponse",
    "WWWAuthenticateChallenge",
    "parse_www_authenticate",
    # Errors
    "AuthConfigError",
    "TokenError",
]
