# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Real-time tool updates without restart.

MCP supports `notifications/tools/list_changed`. When you add, remove,
or modify tools at runtime, connected clients are notified and re-fetch
the tool list automatically.

This enables:
- Feature flag rollouts without deployment
- A/B testing different tool sets
- Multi-tenant servers with dynamic capabilities
- Admin dashboards that enable/disable features live

Architecture:
- MCP server on :8000
- HTTP control API on :8001 (add/remove tools dynamically)

Usage:
    uv run python examples/showcase/03_realtime_server.py
"""

import asyncio
import json
import logging
from typing import Any

import anyio
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
import uvicorn

from dedalus_mcp import MCPServer, tool

# Suppress log noise
for name in ("mcp", "httpx", "uvicorn", "uvicorn.access", "uvicorn.error"):
    logging.getLogger(name).setLevel(logging.WARNING)

server = MCPServer(
    "realtime",
    instructions="Tools can be added/removed at runtime",
    allow_dynamic_tools=True,  # Enable runtime tool registration
)


# Base tools always available
@tool(description="Health check")
def health() -> str:
    return "ok"


@tool(description="Get server time")
def server_time() -> str:
    from datetime import datetime

    return datetime.now().isoformat()


server.collect(health, server_time)


# Track dynamically added tools
dynamic_tools: dict[str, Any] = {}


async def add_tool_handler(request: Request) -> JSONResponse:
    """POST /tools - Add a new tool at runtime."""
    try:
        data = await request.json()
        name = data["name"]
        description = data.get("description", f"Dynamic tool: {name}")

        # Create a dynamic tool function
        async def dynamic_fn(**kwargs: Any) -> dict:
            return {"tool": name, "args": kwargs, "dynamic": True}

        dynamic_fn.__name__ = name

        # Register with server
        decorated = tool(name=name, description=description)(dynamic_fn)
        server.collect(decorated)
        dynamic_tools[name] = decorated

        # Notify connected clients
        await server.notify_tools_list_changed()

        return JSONResponse({"status": "added", "name": name})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


async def remove_tool_handler(request: Request) -> JSONResponse:
    """DELETE /tools/{name} - Remove a tool at runtime."""
    name = request.path_params["name"]

    if name in dynamic_tools:
        # Remove from allow list (effectively hides it)
        current = server.tools.tool_names
        server.tools.allow_tools([n for n in current if n != name])
        del dynamic_tools[name]

        await server.notify_tools_list_changed()
        return JSONResponse({"status": "removed", "name": name})

    return JSONResponse({"error": "Tool not found"}, status_code=404)


async def list_tools_handler(request: Request) -> JSONResponse:
    """GET /tools - List all tools."""
    tools = server.tools.tool_names
    return JSONResponse({"tools": tools, "dynamic": list(dynamic_tools.keys())})


# Control API routes
control_app = Starlette(
    routes=[
        Route("/tools", add_tool_handler, methods=["POST"]),
        Route("/tools/{name}", remove_tool_handler, methods=["DELETE"]),
        Route("/tools", list_tools_handler, methods=["GET"]),
    ]
)


async def start_control_api() -> None:
    """Start the HTTP control API on :8001."""
    config = uvicorn.Config(control_app, host="127.0.0.1", port=8001, log_level="warning")
    server_instance = uvicorn.Server(config)
    await server_instance.serve()


async def main() -> None:
    print("Starting real-time MCP server...")
    print("MCP endpoint: http://127.0.0.1:8000/mcp\n")
    print("Control API: http://127.0.0.1:8001")
    print('  POST /tools        - Add tool: {"name": "...", "description": "..."}')
    print("  DELETE /tools/{n}  - Remove tool")
    print("  GET /tools         - List tools\n")

    async with anyio.create_task_group() as tg:
        tg.start_soon(start_control_api)
        tg.start_soon(server.serve)


if __name__ == "__main__":
    asyncio.run(main())
