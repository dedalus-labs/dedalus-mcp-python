# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Server with rich progress reporting.

Long-running tools can report progress back to the client. This enables
proper loading indicators, progress bars, and cancellation points.

Dedalus MCP handles progress tokens automatically. Just call ctx.progress()
from within your tool.

Usage:
    uv run python examples/showcase/05_progress_server.py
"""

import asyncio
from dedalus_mcp import MCPServer, tool, get_context

server = MCPServer("progress", instructions="I report progress on long operations")


@tool(description="Process items with progress reporting")
async def process_batch(items: list[str]) -> dict:
    """Process each item and report progress."""
    ctx = get_context()
    results = []
    total = len(items)

    for i, item in enumerate(items):
        # Report progress
        await ctx.progress(current=i, total=total, message=f"Processing: {item}")

        # Simulate work
        await asyncio.sleep(0.5)
        results.append({"item": item, "status": "processed"})

    await ctx.progress(current=total, total=total, message="Complete!")
    return {"processed": len(results), "results": results}


@tool(description="Long-running analysis with stages")
async def analyze_data(dataset: str) -> dict:
    """Multi-stage analysis with progress updates."""
    ctx = get_context()
    stages = ["Loading", "Validating", "Transforming", "Analyzing", "Summarizing"]

    for i, stage in enumerate(stages):
        await ctx.progress(current=i, total=len(stages), message=stage)
        await asyncio.sleep(1)  # Simulate work

    await ctx.progress(current=len(stages), total=len(stages), message="Done!")

    return {
        "dataset": dataset,
        "stages_completed": len(stages),
        "summary": f"Analysis of {dataset} complete",
    }


@tool(description="Download with byte-level progress")
async def download_file(url: str) -> dict:
    """Simulate file download with progress."""
    ctx = get_context()
    total_bytes = 10_000_000  # 10 MB
    downloaded = 0
    chunk_size = 500_000

    while downloaded < total_bytes:
        await ctx.progress(
            current=downloaded,
            total=total_bytes,
            message=f"Downloading: {downloaded / 1_000_000:.1f} / {total_bytes / 1_000_000:.1f} MB",
        )
        await asyncio.sleep(0.2)
        downloaded = min(downloaded + chunk_size, total_bytes)

    await ctx.progress(current=total_bytes, total=total_bytes, message="Download complete!")

    return {"url": url, "bytes": total_bytes, "status": "downloaded"}


server.collect(process_batch, analyze_data, download_file)

if __name__ == "__main__":
    asyncio.run(server.serve())

