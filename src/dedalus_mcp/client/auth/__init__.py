# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""OAuth authentication for MCP clients.

This module provides spec-compliant OAuth authentication per MCP authorization spec:
- ClientCredentialsAuth: M2M/backend service authentication
- TokenExchangeAuth: User delegation via token exchange (RFC 8693)
- DeviceCodeAuth: CLI tool authentication (stub)
- AuthorizationCodeAuth: Browser-based authentication (stub)

Example usage:

    # M2M / Backend service
    auth = await ClientCredentialsAuth.from_resource(
        resource_url="https://mcp.example.com/mcp",
        client_id="m2m",
        client_secret=os.environ["M2M_SECRET"],
    )
    await auth.get_token()
    client = await MCPClient.connect("https://mcp.example.com/mcp", auth=auth)

    # User delegation (e.g., from Clerk token)
    auth = await TokenExchangeAuth.from_resource(
        resource_url="https://mcp.example.com/mcp",
        client_id="dedalus-sdk",
        subject_token=clerk_session_token,
    )
    await auth.get_token()
    client = await MCPClient.connect("https://mcp.example.com/mcp", auth=auth)
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
