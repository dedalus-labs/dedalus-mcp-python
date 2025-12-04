# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Accessing request context from tools.

Tools can access the current request context via `get_context()`.
This provides logging, progress reporting, session info, and more.

Usage:
    uv run python examples/capabilities/tools/03_context_access.py
"""

import asyncio
import logging

from dedalus_mcp import MCPServer, get_context, tool

for name in ("mcp", "httpx", "uvicorn"):
    logging.getLogger(name).setLevel(logging.WARNING)

server = MCPServer("context-demo")


@tool(description="Show current session info")
async def whoami() -> dict:
    """Access session and request metadata."""
    ctx = get_context()

    return {
        "request_id": ctx.request_id,
        "session_id": ctx.session_id,
        "has_progress_token": ctx.progress_token is not None,
    }


@tool(description="Tool with logging")
async def process_with_logging(data: str) -> dict:
    """Demonstrate structured logging to client."""
    ctx = get_context()

    # Different log levels
    await ctx.debug("Starting process", data={"input_length": len(data)})
    await ctx.info(f"Processing: {data[:20]}...")

    # Simulate work
    await asyncio.sleep(0.1)

    if len(data) < 3:
        await ctx.warning("Input too short, results may be poor")

    await ctx.info("Processing complete")
    return {"processed": data.upper(), "length": len(data)}


@tool(description="Long task with progress")
async def long_task(steps: int = 5) -> dict:
    """Demonstrate progress tracking."""
    ctx = get_context()

    results = []
    async with ctx.progress(total=steps) as tracker:
        for i in range(steps):
            await tracker.advance(1, message=f"Step {i + 1}/{steps}")
            await asyncio.sleep(0.3)
            results.append(f"step_{i + 1}")

    return {"steps_completed": steps, "results": results}


@tool(description="Batch processing with progress")
async def batch_process(items: list[str]) -> dict:
    """Process items with progress updates."""
    ctx = get_context()
    processed = []

    async with ctx.progress(total=len(items)) as tracker:
        for item in items:
            await ctx.debug(f"Processing item: {item}")
            await tracker.advance(1, message=f"Processing: {item}")
            await asyncio.sleep(0.2)
            processed.append(item.upper())

    await ctx.info(f"Batch complete: {len(processed)} items")
    return {"processed": processed, "count": len(processed)}


server.collect(whoami, process_with_logging, long_task, batch_process)

if __name__ == "__main__":
    print("Context demo server: http://127.0.0.1:8000/mcp")
    print("\nContext features demonstrated:")
    print("  - Request/session metadata (whoami)")
    print("  - Structured logging (process_with_logging)")
    print("  - Progress tracking (long_task, batch_process)")
    asyncio.run(server.serve())
