# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Credential binding configuration for MCP servers.

This example demonstrates how to configure credential bindings for MCP servers
that require external credentials (API keys, tokens, etc.) when used with the
Dedalus SDK.

The pattern:
1. Define an MCPServer with tools
2. Attach Credentials specifying which env vars hold credential values
3. Set the connection name to match keys in the SDK's credentials list
4. SDK encrypts credentials and provisions connection handles
5. Enclave injects decrypted credentials into env vars at dispatch time

Security model:
- Your credentials are encrypted client-side before leaving your machine
- MCP server code only sees env var names, never actual values
- Enclave decrypts and injects at runtime in isolated memory
- Credentials are scrubbed after each request
"""

from __future__ import annotations

import asyncio
import os

from dedalus_mcp import MCPServer, tool
from dedalus_mcp.auth import Binding, Credentials


# --- Basic: Simple API key binding -------------------------------------------


def example_simple_binding() -> MCPServer:
    """Minimal example: single API key."""
    server = MCPServer("openai-chat")

    @tool(description="Chat with OpenAI")
    async def chat(prompt: str) -> str:
        # At runtime, OPENAI_API_KEY will be populated by the enclave
        api_key = os.environ["OPENAI_API_KEY"]
        # ... use api_key to call OpenAI
        return f"Response to: {prompt}"

    server.collect(chat)

    # Bind the credential: tool reads OPENAI_API_KEY env var
    server.credentials = Credentials(api_key="OPENAI_API_KEY")

    # Connection name matches credentials list in SDK
    server.connection = "openai"

    return server


# --- Intermediate: Multiple credentials with options -------------------------


def example_multiple_credentials() -> MCPServer:
    """Multiple credentials with defaults and optional values."""
    server = MCPServer("github-integration")

    @tool(description="Create GitHub issue")
    async def create_issue(repo: str, title: str, body: str) -> str:
        token = os.environ["GITHUB_TOKEN"]
        # Optional: custom API URL for GitHub Enterprise
        api_url = os.environ.get("GITHUB_API_URL", "https://api.github.com")
        # ... create issue
        return f"Created issue in {repo}"

    server.collect(create_issue)

    server.credentials = Credentials(
        # Required: GitHub personal access token
        token="GITHUB_TOKEN",
        # Optional: custom API URL with default
        api_url=Binding("GITHUB_API_URL", default="https://api.github.com"),
        # Optional: organization scope (may not be provided)
        org=Binding("GITHUB_ORG", optional=True),
    )

    server.connection = "github"

    return server


# --- Advanced: Typed bindings with casting -----------------------------------


def example_typed_bindings() -> MCPServer:
    """Bindings with type casting for non-string values."""
    server = MCPServer("database-connector")

    @tool(description="Query database")
    async def query(sql: str) -> list[dict]:
        host = os.environ["DB_HOST"]
        port = int(os.environ["DB_PORT"])  # Cast handled by binding
        timeout = int(os.environ.get("DB_TIMEOUT", "30"))
        # ... execute query
        return []

    server.collect(query)

    server.credentials = Credentials(
        host="DB_HOST",
        port=Binding("DB_PORT", cast=int),
        timeout=Binding("DB_TIMEOUT", cast=int, default=30),
        password="DB_PASSWORD",
    )

    server.connection = "database"

    return server


# --- Usage with Dedalus SDK --------------------------------------------------


async def example_sdk_usage() -> None:
    """How this integrates with the Dedalus SDK.

    Note: This is pseudo-code showing the SDK integration pattern.
    The actual Dedalus SDK import would be `from dedalus_labs import Dedalus`.
    """
    # Create server with bindings
    openai_server = example_simple_binding()
    github_server = example_multiple_credentials()

    # SDK usage (pseudo-code):
    #
    # from dedalus_labs import Dedalus, Credential
    #
    # client = Dedalus(
    #     api_key="dsk-...",
    #     credentials=[
    #         # Credentials match server.connection values
    #         Credential(openai_conn, api_key="sk-..."),
    #         Credential(github_conn, token="ghp-...", org="my-org"),
    #     ],
    #     mcp_servers=[openai_server, github_server],
    # )
    #
    # # SDK automatically:
    # # 1. Matches server.connection -> credentials
    # # 2. Encrypts credential values with enclave public key
    # # 3. Provisions connection handles
    # # 4. Stores handle on server for dispatch

    print("Server configurations:")
    print(f"  openai-chat credentials: {openai_server.credentials.to_dict()}")
    print(f"  github-integration credentials: {github_server.credentials.to_dict()}")


# --- Wire format inspection --------------------------------------------------


def show_wire_format() -> None:
    """Show what the serialized credentials look like."""
    server = example_multiple_credentials()

    print("Wire format for credentials:")
    print(server.credentials.to_dict())
    # Output:
    # {
    #     "token": "GITHUB_TOKEN",
    #     "api_url": {"name": "GITHUB_API_URL", "default": "https://api.github.com"},
    #     "org": {"name": "GITHUB_ORG", "optional": True}
    # }


if __name__ == "__main__":
    print("=== Credential Binding Examples ===\n")

    print("1. Simple binding:")
    server1 = example_simple_binding()
    print(f"   credentials: {server1.credentials.to_dict()}\n")

    print("2. Multiple credentials:")
    server2 = example_multiple_credentials()
    print(f"   credentials: {server2.credentials.to_dict()}\n")

    print("3. Typed bindings:")
    server3 = example_typed_bindings()
    print(f"   credentials: {server3.credentials.to_dict()}\n")

    print("4. Wire format inspection:")
    show_wire_format()
