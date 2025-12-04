# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Client that reacts to real-time tool updates.

When the server emits `notifications/tools/list_changed`, this client
re-fetches the tool list. Watch tools appear and disappear live.

Usage:
    # Terminal 1: Start the server
    uv run python examples/showcase/03_realtime_server.py

    # Terminal 2: Run this client (watches for updates)
    uv run python examples/showcase/03_realtime_client.py

    # Terminal 3: Add tools via the control API
    curl -X POST http://127.0.0.1:8001/tools \
         -H "Content-Type: application/json" \
         -d '{"name": "greet", "description": "Say hello"}'

    # Watch Terminal 2 update automatically!
"""

import asyncio
import logging
import httpx
from dedalus_mcp.client import MCPClient

# Suppress log noise
for name in ("mcp", "httpx"):
    logging.getLogger(name).setLevel(logging.WARNING)


async def add_tool_via_api(name: str, description: str) -> None:
    """Add a tool via the control API."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "http://127.0.0.1:8001/tools",
            json={"name": name, "description": description},
        )
        print(f"API Response: {resp.json()}")


async def remove_tool_via_api(name: str) -> None:
    """Remove a tool via the control API."""
    async with httpx.AsyncClient() as client:
        resp = await client.delete(f"http://127.0.0.1:8001/tools/{name}")
        print(f"API Response: {resp.json()}")


async def main() -> None:
    print("Connecting to real-time MCP server...")
    client = await MCPClient.connect("http://127.0.0.1:8000/mcp")

    print(f"Connected to: {client.initialize_result.serverInfo.name}")

    # Initial tool list
    tools = await client.list_tools()
    print(f"Initial tools: {[t.name for t in tools.tools]}\n")

    print("--- Demo: Adding and removing tools at runtime ---\n")

    # Add a tool
    print("Adding 'calculator' tool via control API...")
    await add_tool_via_api("calculator", "Perform calculations")

    # Give server time to notify
    await asyncio.sleep(0.5)

    # Check updated list
    tools = await client.list_tools()
    print(f"Tools after add: {[t.name for t in tools.tools]}")

    # Call the new tool
    result = await client.call_tool("calculator", {"x": 10, "y": 5})
    print(f"calculator({{'x': 10, 'y': 5}}) = {result.structuredContent}\n")

    # Add another
    print("Adding 'translate' tool via control API...")
    await add_tool_via_api("translate", "Translate text between languages")

    await asyncio.sleep(0.5)
    tools = await client.list_tools()
    print(f"Tools after add: {[t.name for t in tools.tools]}\n")

    # Remove a tool
    print("Removing 'calculator' tool via control API...")
    await remove_tool_via_api("calculator")

    await asyncio.sleep(0.5)
    tools = await client.list_tools()
    print(f"Tools after remove: {[t.name for t in tools.tools]}\n")

    await client.close()
    print("Demo complete!")


if __name__ == "__main__":
    asyncio.run(main())
