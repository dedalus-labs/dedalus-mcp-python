# ==============================================================================
#                  © 2025 Dedalus Labs, Inc. and affiliates
#                            Licensed under MIT
#               github.com/dedalus-labs/openmcp-python/LICENSE
# ==============================================================================

"""Dynamic tool registration via webhook.

Demonstrates hot-reloading of tool definitions at runtime without restarting
the MCP server. The server listens on a secondary TCP port for JSON config
payloads that update the allow-list and register new inline tools on the fly.

Pattern:
1. Server starts with permissive allow-list (all tools visible)
2. POST JSON config to the webhook endpoint to update tool registry
3. Server calls `notify_tools_list_changed()` to inform connected clients
4. Clients re-fetch tool list to discover new/removed tools

Use cases:
- Feature flag rollouts that add/remove tools without deployment
- Multi-tenant servers where tool sets vary per customer configuration
- A/B testing different tool sets
- Dynamic policy enforcement (enable/disable tools based on external events)

Config format:
    {
      "allow": ["tool1", "tool2"],  # null = allow all
      "inline_tools": [
        {"name": "dynamic_echo", "tags": ["beta"]}
      ]
    }

Note: This example shows the reconciliation logic. Production servers should
use authenticated HTTP endpoints (e.g., FastAPI routes) instead of raw TCP.

Usage:
    python examples/dynamic_server.py
    # In another terminal:
    echo '{"allow":["health_check"],"inline_tools":[{"name":"test","tags":[]}]}' | nc localhost 9000
"""

from __future__ import annotations

import json
import logging
from typing import Any

import anyio
from anyio import create_task_group
from anyio.abc import SocketStream

from openmcp import MCPServer, tool

# Suppress SDK and server logs for cleaner demo output
for logger_name in ("mcp", "httpx", "uvicorn", "uvicorn.access", "uvicorn.error"):
    logging.getLogger(logger_name).setLevel(logging.CRITICAL)

server = MCPServer("webhook-driven", instructions="Hot-reload tools from controller")
server.allow_tools(None)  # start in permissive mode

# Register a baseline tool to demonstrate allow-list filtering
with server.binding():

    @tool(description="Basic health check endpoint")
    def health_check() -> str:
        return "ok"


async def reconcile_tools(config: dict[str, Any]) -> None:
    """Update server tool registry from external configuration.

    Args:
        config: Dict with "allow" (list of tool names or None) and
                "inline_tools" (list of tool specs with name/tags)
    """
    allow = set(config.get("allow", [])) or None
    server.allow_tools(allow)

    # Dynamically define or update inline tools from the payload
    for spec in config.get("inline_tools", []):
        name = spec["name"]
        tags = set(spec.get("tags", ()))

        async def dynamic_tool(**kwargs: Any) -> dict[str, Any]:
            return {"name": name, "args": kwargs}

        dynamic_tool.__name__ = name
        with server.binding():
            tool(name=name, tags=tags)(dynamic_tool)

    await server.notify_tools_list_changed()


async def webhook_listener(port: int) -> None:
    """Listen for JSON payloads on a raw TCP socket to update tool config."""

    async def handle_client(stream: SocketStream) -> None:
        data = await stream.receive(65536)
        payload = data.decode("utf-8")
        config = json.loads(payload)
        await reconcile_tools(config)
        await stream.send(b"HTTP/1.1 204 No Content\r\n\r\n")

    listeners = await anyio.create_tcp_listener(local_host="127.0.0.1", local_port=port)
    async with listeners:
        await listeners.serve(handle_client)


async def main() -> None:
    async with create_task_group() as tg:
        tg.start_soon(server.serve, "streamable-http", False, "critical")
        tg.start_soon(webhook_listener, 9000)


if __name__ == "__main__":
    anyio.run(main)
