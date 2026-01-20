# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""DPoP authentication for protected MCP servers.

Bearer tokens are bearer instruments - steal one and you have full access.
DPoP binds tokens to a keypair. Each request includes a fresh proof signed
by your key. Stolen tokens are useless without the private key.

Usage:
    uv run python examples/client/dpop_auth.py
"""

from __future__ import annotations

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import ec

from dedalus_mcp.client import DPoPAuth, MCPClient


# In production: load from secure storage
# This key must match the one used when obtaining the access token
DPOP_KEY = ec.generate_private_key(ec.SECP256R1(), default_backend())

# In production: obtain from authorization server via PKCE flow
ACCESS_TOKEN = "your_dpop_bound_access_token"

SERVER_URL = "https://mcp.example.com/mcp"


async def main() -> None:
    # Create DPoP auth handler
    auth = DPoPAuth(access_token=ACCESS_TOKEN, dpop_key=DPOP_KEY)

    # Verify thumbprint matches token's cnf.jkt claim
    print(f"DPoP key thumbprint: {auth.thumbprint}")

    # Connect with DPoP auth
    client = await MCPClient.connect(SERVER_URL, auth=auth)

    try:
        print(f"Connected: {client.initialize_result.serverInfo.name}")

        # All requests automatically include DPoP headers
        tools = await client.list_tools()
        print(f"Tools: {[t.name for t in tools.tools]}")

    finally:
        await client.close()


async def with_token_refresh() -> None:
    """Handle token refresh without recreating the auth handler."""
    auth = DPoPAuth(access_token=ACCESS_TOKEN, dpop_key=DPOP_KEY)
    client = await MCPClient.connect(SERVER_URL, auth=auth)

    try:
        # ... use client ...

        # When token expires, refresh and update
        new_token = await refresh_token_from_as()  # Your implementation
        auth.set_access_token(new_token)

        # Subsequent requests use the new token
        await client.list_tools()

    finally:
        await client.close()


async def with_server_nonce() -> None:
    """Handle server-required nonces (RFC 9449 §8)."""
    auth = DPoPAuth(access_token=ACCESS_TOKEN, dpop_key=DPOP_KEY)
    client = await MCPClient.connect(SERVER_URL, auth=auth)

    try:
        # If server returns DPoP-Nonce header in 401 response,
        # update the nonce and retry
        auth.set_nonce("server_provided_nonce")

        # Subsequent proofs include the nonce
        await client.list_tools()

    finally:
        await client.close()


async def refresh_token_from_as() -> str:
    """Placeholder: implement your OAuth refresh flow."""
    return "refreshed_token"


if __name__ == "__main__":
    print("Note: This example requires a protected server and valid token.")
    print("Update SERVER_URL and ACCESS_TOKEN before running.")
    # asyncio.run(main())
