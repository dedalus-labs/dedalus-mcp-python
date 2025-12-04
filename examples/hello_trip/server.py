# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Minimal end-to-end MCP server demo.

Demonstrates the complete server lifecycle with tools, resources, and prompts as
specified in docs/mcp/core/lifecycle/lifecycle-phases.md. Each capability maps to
its corresponding spec section:

- Tools: docs/mcp/spec/schema-reference/tools-*.md
- Resources: docs/mcp/spec/schema-reference/resources-*.md
- Prompts: docs/mcp/spec/schema-reference/prompts-*.md

The server exposes:

* Tool ``plan_trip`` – travel plan with progress tracking and logging
* Resource ``travel://tips/barcelona`` – static travel tips (resources-read.md)
* Prompt ``plan-vacation`` – demonstrates prompt rendering (prompts-get.md)

Usage::

    uv run python examples/hello_trip/server.py --transport stdio
    uv run python examples/hello_trip/server.py --transport streamable-http

Try it alongside ``client.py`` to see the full flow.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from dedalus_mcp import MCPServer, get_context, prompt, resource, tool

# Suppress logs for cleaner demo output
for logger_name in ("mcp", "httpx", "uvicorn", "uvicorn.access", "uvicorn.error"):
    logging.getLogger(logger_name).setLevel(logging.CRITICAL)


@tool(
    description="Summarize a travel plan",
    tags={"travel", "demo"},
    output_schema={
        "type": "object",
        "properties": {"summary": {"type": "string"}, "suggestion": {"type": "string"}},
        "required": ["summary"],
    },
)
async def plan_trip(destination: str, days: int, budget: float) -> dict[str, Any]:
    ctx = get_context()
    await ctx.info("planning trip", data={"destination": destination, "days": days, "budget": budget})

    async with ctx.progress(total=3) as tracker:
        await tracker.advance(1, message="Gathering highlights")
        await asyncio.sleep(0)
        await tracker.advance(1, message="Estimating costs")
        await asyncio.sleep(0)
        await tracker.advance(1, message="Summarising itinerary")

    summary = f"Plan: {days} days in {destination} with budget ${budget:.2f}."
    result = {"summary": summary, "suggestion": "Remember to book tickets early!"}
    await ctx.debug("plan complete", data=result)
    return result


@resource(uri="travel://tips/barcelona", name="Barcelona Tips", mime_type="text/plain")
def barcelona_tips() -> str:
    return "Visit Sagrada Família, explore the Gothic Quarter, and enjoy tapas on La Rambla."


@prompt(name="plan-vacation", description="Guide the model through planning a trip")
def plan_vacation_prompt(args: dict[str, str]) -> list[dict[str, str]]:
    destination = args.get("destination", "unknown destination")
    return [
        {
            "role": "assistant",
            "content": "You are a helpful travel planner. Summarize the itinerary and call tools if needed.",
        },
        {"role": "user", "content": f"Plan a vacation to {destination}."},
    ]


server = MCPServer("hello-trip")
server.collect(plan_trip, barcelona_tips, plan_vacation_prompt)


async def main(transport: str = "streamable-http") -> None:
    """Serve the hello-trip MCP server on the specified transport."""
    kwargs = {"transport": transport}
    if transport == "streamable-http":
        kwargs.update({"verbose": False, "log_level": "critical", "uvicorn_options": {"access_log": False}})
    await server.serve(**kwargs)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run the hello-trip MCP server")
    parser.add_argument(
        "--transport", default="streamable-http", choices=["streamable-http", "stdio"], help="Transport to use"
    )
    args = parser.parse_args()

    asyncio.run(main(args.transport))
