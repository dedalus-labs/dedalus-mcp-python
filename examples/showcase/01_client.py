# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Minimal MCP client.

Connect, list tools, call one, disconnect. No context managers required.

Usage:
    # Terminal 1: Start the server
    uv run python examples/showcase/01_minimal.py

    # Terminal 2: Run this client
    uv run python examples/showcase/01_client.py
"""

import asyncio
import logging
from dedalus_mcp.client import MCPClient

# Suppress log noise for clean output
for name in ("mcp", "httpx"):
    logging.getLogger(name).setLevel(logging.WARNING)


async def main() -> None:
    client = await MCPClient.connect("http://127.0.0.1:8000/mcp")

    print(f"Connected to: {client.initialize_result.serverInfo.name}")

    tools = await client.list_tools()
    print(f"Available tools: {[t.name for t in tools.tools]}")

    result = await client.call_tool("add", {"a": 40, "b": 2})
    print(f"add(40, 2) = {result.content[0].text}")

    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
