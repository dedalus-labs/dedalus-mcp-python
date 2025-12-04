# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Multi-server patterns: same tools, different configurations.

Dedalus MCP's decoupled registration shines here. Define tools once,
register them to multiple servers with different settings.

Use cases:
- Production vs staging servers
- Public vs internal APIs
- Feature-flagged tool sets
- Multi-tenant deployments

Usage:
    uv run python examples/patterns/multi_server.py
"""

import asyncio
import logging

import anyio

from dedalus_mcp import MCPServer, tool

for name in ("mcp", "httpx", "uvicorn"):
    logging.getLogger(name).setLevel(logging.WARNING)


# ============================================================================
# Shared tools (defined once, used everywhere)
# ============================================================================


@tool(description="Add two numbers", tags={"math", "safe"})
def add(a: int, b: int) -> int:
    return a + b


@tool(description="Multiply two numbers", tags={"math", "safe"})
def multiply(a: int, b: int) -> int:
    return a * b


@tool(description="Delete a record", tags={"database", "dangerous"})
def delete_record(table: str, id: int) -> dict:
    return {"deleted": True, "table": table, "id": id}


@tool(description="Execute raw SQL", tags={"database", "dangerous", "admin"})
def execute_sql(query: str) -> dict:
    return {"executed": True, "query": query}


@tool(description="Get system status", tags={"system", "safe"})
def status() -> dict:
    return {"status": "healthy", "version": "1.0.0"}


@tool(description="Shutdown server", tags={"system", "admin", "dangerous"})
def shutdown() -> dict:
    return {"shutdown": "initiated"}


# ============================================================================
# Multiple servers with different tool sets
# ============================================================================


def create_public_server() -> MCPServer:
    """Public API: safe tools only."""
    server = MCPServer("public-api", instructions="Public API with safe operations only")

    # Register only safe tools
    server.collect(add, multiply, status)

    return server


def create_internal_server() -> MCPServer:
    """Internal API: all tools, but filter dangerous ones."""
    server = MCPServer("internal-api", instructions="Internal API for staff")

    # Register all tools
    server.collect(add, multiply, delete_record, execute_sql, status, shutdown)

    # But hide the most dangerous ones by default
    server.tools.allow_tools(["add", "multiply", "delete_record", "status"])

    return server


def create_admin_server() -> MCPServer:
    """Admin API: everything, no restrictions."""
    server = MCPServer("admin-api", instructions="Admin API with full access")

    # Register everything
    server.collect(add, multiply, delete_record, execute_sql, status, shutdown)

    # No filtering
    return server


# ============================================================================
# Run all three servers
# ============================================================================


async def main() -> None:
    public = create_public_server()
    internal = create_internal_server()
    admin = create_admin_server()

    print("=" * 60)
    print("Multi-Server Demo: Same tools, different configurations")
    print("=" * 60)
    print("\nServers:")
    print(f"  Public   (:8000) - Tools: {public.tools.tool_names}")
    print(f"  Internal (:8001) - Tools: {internal.tools.tool_names}")
    print(f"  Admin    (:8002) - Tools: {admin.tools.tool_names}")
    print("\nAll use the SAME decorated functions.")
    print("No code duplication. Just different server.collect() calls.")
    print("\n" + "=" * 60)

    async with anyio.create_task_group() as tg:
        tg.start_soon(public.serve, "streamable-http", 8000)
        tg.start_soon(internal.serve, "streamable-http", 8001)
        tg.start_soon(admin.serve, "streamable-http", 8002)


if __name__ == "__main__":
    asyncio.run(main())

