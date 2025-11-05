# ==============================================================================
#                  © 2025 Dedalus Labs, Inc. and affiliates
#                            Licensed under MIT
#               github.com/dedalus-labs/openmcp-python/LICENSE
# ==============================================================================

"""Minimal tool registration with automatic schema inference.

Demonstrates the simplest tool patterns with OpenMCP: sync/async functions
with type-hinted parameters automatically generate JSON Schema without
explicit decoration. This is the foundation for all tool-based MCP servers.

Pattern:
- @tool decorator registers functions as MCP tools
- Type hints → JSON Schema (parameters + return type)
- Sync and async functions work identically
- No schema boilerplate required

When to use:
- Starting point for any MCP server with tools
- APIs, computations, or data retrieval
- Functions with well-defined inputs/outputs

Spec: https://modelcontextprotocol.io/specification/2025-06-18/server/tools
Usage: uv run python examples/tools/basic_tool.py
"""

from __future__ import annotations

import asyncio
import logging

from openmcp import MCPServer, tool

# Suppress logs for clean demo output
for logger_name in ("mcp", "httpx", "uvicorn", "uvicorn.access", "uvicorn.error"):
    logging.getLogger(logger_name).setLevel(logging.CRITICAL)

server = MCPServer("basic-tools")


with server.binding():

    @tool(description="Add two integers")
    def add(a: int, b: int) -> int:
        """Schema inferred: a and b as required integers, returns int."""
        return a + b

    @tool(description="Greet a user by name")
    async def greet(name: str) -> str:
        """Async tools work identically. Schema: name (required str) → str."""
        return f"Hello, {name}!"

    @tool(description="Return structured data")
    def get_user_info(user_id: int) -> dict[str, str | int]:
        """Schema infers dict[str, str | int] as output type."""
        return {"id": user_id, "username": f"user_{user_id}", "status": "active"}


async def main() -> None:
    await server.serve(transport="streamable-http", verbose=False, log_level="critical")


if __name__ == "__main__":
    asyncio.run(main())
