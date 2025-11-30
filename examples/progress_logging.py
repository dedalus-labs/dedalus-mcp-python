# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Progress tracking and logging demonstration.

Shows how to use MCP's logging and progress notification primitives within
tool execution. The server reports structured log events and granular progress
updates back to the client during long-running operations.

Key patterns demonstrated:
- Structured logging via `ctx.info()` with arbitrary JSON-serializable data
- Progress tracking with `ctx.progress()` context manager
- Async progress updates via `tracker.advance()`

Context is automatically injected per-request; call `get_context()` inside any
tool to access logging and progress APIs. See spec details at:
- https://spec.modelcontextprotocol.io/specification/2025-11-05/server/utilities/logging
- https://spec.modelcontextprotocol.io/specification/2025-11-05/server/utilities/progress

Usage:
    python examples/progress_logging.py
"""

from __future__ import annotations

import asyncio
import logging

from openmcp import MCPServer, get_context, tool

# Suppress SDK and server logs for cleaner demo output
for logger_name in ("mcp", "httpx", "uvicorn", "uvicorn.access", "uvicorn.error"):
    logging.getLogger(logger_name).setLevel(logging.CRITICAL)

server = MCPServer("progress-demo")

with server.binding():

    @tool(description="Processes a batch of items with progress tracking")
    async def process(batch: list[str]) -> str:
        """Process items one by one, reporting progress after each.

        Args:
            batch: List of item identifiers to process

        Returns:
            Status message confirming completion
        """
        ctx = get_context()
        await ctx.info("batch start", data={"size": len(batch)})
        async with ctx.progress(total=len(batch)) as tracker:
            for item in batch:
                await tracker.advance(1, message=f"done {item}")
        await ctx.info("batch complete")
        return "ok"


async def main() -> None:
    await server.serve(verbose=False, log_level="critical")


if __name__ == "__main__":
    asyncio.run(main())
