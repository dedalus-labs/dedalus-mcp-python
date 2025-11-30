# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Long-running tool with progress tracking.

Demonstrates incremental progress reporting for async operations. Clients
receive notifications/progress updates during execution, enabling UI
progress bars and status displays. Requires client to supply progressToken.

Pattern:
- async with ctx.progress(total=N) as tracker
- await tracker.advance(delta, message="...")
- Framework sends notifications/progress to client
- ctx.info/debug for structured logging

When to use:
- Operations > 1 second duration
- Batch processing with known item counts
- Network requests with incremental updates
- User feedback during long computations

Spec: https://modelcontextprotocol.io/specification/2025-06-18/basic/utilities/progress
Usage: uv run python examples/tools/progress_tool.py
"""

from __future__ import annotations

import asyncio
import logging

from openmcp import MCPServer, get_context, tool

# Suppress logs for clean demo output
for logger_name in ("mcp", "httpx", "uvicorn", "uvicorn.access", "uvicorn.error"):
    logging.getLogger(logger_name).setLevel(logging.CRITICAL)

server = MCPServer("progress-demo")


with server.binding():

    @tool(description="Process a batch of items with progress")
    async def batch_process(items: list[str], delay: float = 0.5) -> dict[str, int]:
        """Report progress for each item processed.

        The client must supply _meta.progressToken or ctx.progress() raises ValueError.
        """
        ctx = get_context()
        await ctx.info("batch started", data={"count": len(items)})

        processed = 0
        async with ctx.progress(total=len(items)) as tracker:
            for item in items:
                # Simulate work
                await asyncio.sleep(delay)
                processed += 1
                await tracker.advance(1, message=f"processed {item}")

        await ctx.info("batch complete", data={"processed": processed})
        return {"total": len(items), "processed": processed}


async def main() -> None:
    await server.serve(transport="streamable-http", verbose=False, log_level="critical")


if __name__ == "__main__":
    asyncio.run(main())
