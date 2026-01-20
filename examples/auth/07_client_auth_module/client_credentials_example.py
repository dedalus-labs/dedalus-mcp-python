#!/usr/bin/env python3
# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Example: Client Credentials Authentication with the new auth module.

This demonstrates the simplified OAuth 2.0 client credentials flow using
the new `dedalus_mcp.client.auth` module.

Usage:
    # Set the M2M secret (or pass via --client-secret)
    export MCP_CLIENT_SECRET="your-m2m-secret"

    # Run the example
    uv run python examples/auth/07_client_auth_module/client_credentials_example.py

    # Or with explicit args
    uv run python examples/auth/07_client_auth_module/client_credentials_example.py \
        --issuer https://preview.as.dedaluslabs.ai \
        --client-id m2m \
        --client-secret "your-secret"
"""

from __future__ import annotations

import argparse
import asyncio
import os

from dedalus_mcp.client.auth import ClientCredentialsAuth, TokenError, fetch_authorization_server_metadata


# Defaults for preview environment
DEFAULT_ISSUER = os.getenv("AS_ISSUER", "https://preview.as.dedaluslabs.ai")
DEFAULT_CLIENT_ID = os.getenv("MCP_CLIENT_ID", "m2m")
DEFAULT_CLIENT_SECRET = os.getenv("MCP_CLIENT_SECRET")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Client Credentials Auth Example", formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--issuer", default=DEFAULT_ISSUER, help=f"Authorization Server issuer URL (default: {DEFAULT_ISSUER})"
    )
    parser.add_argument(
        "--client-id", default=DEFAULT_CLIENT_ID, help=f"OAuth client ID (default: {DEFAULT_CLIENT_ID})"
    )
    parser.add_argument(
        "--client-secret", default=DEFAULT_CLIENT_SECRET, help="OAuth client secret (default: MCP_CLIENT_SECRET env)"
    )
    parser.add_argument("--scope", default=None, help="Optional scope to request")
    return parser


async def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if not args.client_secret:
        parser.error("Provide --client-secret or set MCP_CLIENT_SECRET")

    print(f"Fetching AS metadata from {args.issuer}...")
    print()

    # Approach 1: Direct construction with AS metadata
    # Use this when you know the AS URL upfront
    import httpx

    async with httpx.AsyncClient() as client:
        server_metadata = await fetch_authorization_server_metadata(client, args.issuer)

    print("Authorization Server Metadata:")
    print(f"  Issuer: {server_metadata.issuer}")
    print(f"  Token Endpoint: {server_metadata.token_endpoint}")
    print(f"  Supported Grants: {server_metadata.grant_types_supported}")
    print()

    # Create auth instance
    auth = ClientCredentialsAuth(
        server_metadata=server_metadata, client_id=args.client_id, client_secret=args.client_secret, scope=args.scope
    )

    print(f"Requesting token for client '{auth.client_id}'...")

    try:
        token = await auth.get_token()
    except TokenError as e:
        print(f"Token request failed: {e}")
        return

    print()
    print("Token acquired successfully!")
    print(f"  Token Type: {token.token_type}")
    print(f"  Expires In: {token.expires_in} seconds")
    print(f"  Access Token: {token.access_token[:50]}...")
    print()

    # Demonstrate token caching
    print("Requesting token again (should be cached)...")
    token2 = await auth.get_token()
    assert token.access_token == token2.access_token
    print("Token was cached correctly.")
    print()

    # Show how to use with MCPClient
    print("=" * 60)
    print("Integration with MCPClient:")
    print("=" * 60)
    print("""
# With the new auth module, connecting to a protected MCP server is simple:

from dedalus_mcp.client import MCPClient
from dedalus_mcp.client.auth import ClientCredentialsAuth

# Option 1: Auto-discovery from protected resource
auth = await ClientCredentialsAuth.from_resource(
    resource_url="https://mcp.example.com/mcp",
    client_id="m2m",
    client_secret=os.environ["M2M_SECRET"],
)
await auth.get_token()
client = await MCPClient.connect("https://mcp.example.com/mcp", auth=auth)

# Option 2: Direct construction (when you know the AS)
server_metadata = await fetch_authorization_server_metadata(http, "https://as.example.com")
auth = ClientCredentialsAuth(
    server_metadata=server_metadata,
    client_id="m2m",
    client_secret=secret,
)
await auth.get_token()
client = await MCPClient.connect("https://mcp.example.com/mcp", auth=auth)
""")


if __name__ == "__main__":
    asyncio.run(main())
