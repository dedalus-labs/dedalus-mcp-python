# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Script-style client connection without context managers.

Demonstrates the simplest way to connect to an MCP server: call connect(),
use the client, call close(). No nesting, no ceremony. This is the primary
API for scripts and applications that manage their own lifecycles.

Pattern:
- MCPClient.connect() returns an already-initialized client
- Use client methods directly (list_tools, call_tool, etc.)
- Call close() when done, or use async with for automatic cleanup

When to use:
- Scripts that need MCP functionality
- Applications with their own lifecycle management
- Testing and exploration

Usage:
    # Start a server first:
    uv run python examples/tools/basic_tool.py

    # Then run this client:
    uv run python examples/client/basic_connect.py
"""

from __future__ import annotations

import asyncio

from dedalus_mcp.client import MCPClient

SERVER_URL = "http://127.0.0.1:8000/mcp"


async def main() -> None:
    # Connect and get an initialized client
    client = await MCPClient.connect(SERVER_URL)

    try:
        # Protocol info
        print(f"Connected: {client.initialize_result.serverInfo.name}")
        print(f"Protocol: {client.initialize_result.protocolVersion}")

        # List tools
        tools = await client.list_tools()
        print(f"Tools: {[t.name for t in tools.tools]}")

        # Call a tool
        result = await client.call_tool("add", {"a": 5, "b": 3})
        print(f"add(5, 3) = {result.content}")

    finally:
        # Always close when done
        await client.close()


async def main_with_context() -> None:
    """Alternative: context manager for automatic cleanup."""
    async with await MCPClient.connect(SERVER_URL) as client:
        tools = await client.list_tools()
        print(f"Tools: {[t.name for t in tools.tools]}")


if __name__ == "__main__":
    asyncio.run(main())
