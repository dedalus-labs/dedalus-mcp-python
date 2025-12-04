# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Bearer token authentication for protected MCP servers.

Demonstrates simple OAuth 2.0 Bearer token auth. Use this for servers
that don't require DPoP sender-constraining. The token is sent as-is
in the Authorization header.

Pattern:
- Obtain access token from authorization server
- Pass BearerAuth to connect()
- Token included in every request automatically

When to use:
- Standard OAuth 2.0/2.1 protected servers
- APIs that don't require DPoP
- Development and testing

Wire format (per RFC 6750):
    Authorization: Bearer {access_token}

Usage:
    # Requires a protected server and valid token
    uv run python examples/client/bearer_auth.py
"""

from __future__ import annotations

import asyncio

from dedalus_mcp.client import BearerAuth, MCPClient

# In production: obtain from authorization server
ACCESS_TOKEN = "your_oauth_access_token"

SERVER_URL = "https://mcp.example.com/mcp"


async def main() -> None:
    # Create Bearer auth handler
    auth = BearerAuth(access_token=ACCESS_TOKEN)

    # Connect with Bearer auth
    client = await MCPClient.connect(SERVER_URL, auth=auth)

    try:
        print(f"Connected: {client.initialize_result.serverInfo.name}")

        # All requests include Authorization: Bearer header
        tools = await client.list_tools()
        print(f"Tools: {[t.name for t in tools.tools]}")

    finally:
        await client.close()


async def with_token_refresh() -> None:
    """Handle token refresh without recreating the client."""
    auth = BearerAuth(access_token=ACCESS_TOKEN)
    client = await MCPClient.connect(SERVER_URL, auth=auth)

    try:
        # ... use client ...

        # When token expires, refresh and update
        new_token = await refresh_token()  # Your implementation
        auth.set_access_token(new_token)

        # Subsequent requests use the new token
        await client.list_tools()

    finally:
        await client.close()


async def refresh_token() -> str:
    """Placeholder: implement your OAuth refresh flow."""
    return "refreshed_token"


if __name__ == "__main__":
    print("Note: This example requires a protected server and valid token.")
    print("Update SERVER_URL and ACCESS_TOKEN before running.")
    # asyncio.run(main())

