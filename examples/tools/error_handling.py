# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Error handling and validation patterns for tools.

Demonstrates two error approaches: exception-based (automatic wrapping) and
explicit CallToolResult (fine-grained control). Framework catches exceptions
and converts to isError=True results. Use explicit results for custom error
metadata or when exceptions don't fit the pattern.

Pattern:
- raise ValueError/Exception -> auto-wrapped as CallToolResult(isError=True)
- return CallToolResult(isError=True, ...) -> explicit error control
- ctx.error/warning for structured logging
- Framework handles JSON-RPC error codes

When to use:
- Input validation (raise ValueError)
- Resource not found (explicit CallToolResult)
- Custom error metadata (error codes, hints)
- Logging errors for observability

Spec: https://modelcontextprotocol.io/specification/2025-06-18/server/tools
Usage: uv run python examples/tools/error_handling.py
"""

from __future__ import annotations

import asyncio
import logging

from openmcp import MCPServer, get_context, tool
from openmcp.types import CallToolResult, TextContent

# Suppress logs for clean demo output
for logger_name in ("mcp", "httpx", "uvicorn", "uvicorn.access", "uvicorn.error"):
    logging.getLogger(logger_name).setLevel(logging.CRITICAL)

server = MCPServer("error-handling")


with server.binding():

    @tool(description="Divide two numbers with validation")
    async def divide(a: float, b: float) -> float:
        """Raise ValueError for invalid inputs (zero division).

        Framework catches exceptions and wraps them in CallToolResult with isError=True.
        """
        if b == 0:
            ctx = get_context()
            await ctx.error("division by zero", data={"a": a, "b": b})
            raise ValueError("Cannot divide by zero")
        return a / b

    @tool(description="Fetch user with explicit error result")
    async def fetch_user(user_id: int) -> CallToolResult | dict[str, str]:
        """Return CallToolResult explicitly for richer error control."""
        ctx = get_context()

        if user_id <= 0:
            await ctx.warning("invalid user_id", data={"user_id": user_id})
            return CallToolResult(content=[TextContent(type="text", text="User ID must be positive")], isError=True)

        # Simulate not found
        if user_id == 999:
            await ctx.info("user not found", data={"user_id": user_id})
            return CallToolResult(content=[TextContent(type="text", text=f"User {user_id} not found")], isError=True)

        return {"id": str(user_id), "name": f"User {user_id}"}


async def main() -> None:
    await server.serve(transport="streamable-http", verbose=False, log_level="critical")


if __name__ == "__main__":
    asyncio.run(main())
