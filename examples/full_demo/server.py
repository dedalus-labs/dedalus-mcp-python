# ==============================================================================
#                  © 2025 Dedalus Labs, Inc. and affiliates
#                            Licensed under MIT
#               github.com/dedalus-labs/openmcp-python/LICENSE
# ==============================================================================

"""Full capability demo server.

Demonstrates all MCP server capabilities per docs/mcp/core/understanding-mcp-servers.md:

1. Tools (docs/mcp/spec/schema-reference/tools-*.md)
   - add: basic tool with progress tracking
   - sleep: demonstrates long-running operations with progress updates

2. Resources (docs/mcp/spec/schema-reference/resources-*.md)
   - resource://time: dynamic resource with live timestamp

3. Prompts (docs/mcp/spec/schema-reference/prompts-*.md)
   - plan-vacation: demonstrates prompt templates with arguments

4. Completion (docs/mcp/capabilities/completion/completion-complete.md)
   - Context-aware completion for prompt arguments

5. Sampling (docs/mcp/capabilities/sampling/*.md)
   - Custom sampling handler override

6. Elicitation (docs/mcp/spec/schema-reference/elicitation-*.md)
   - User input elicitation handler

Also demonstrates notification support for capability changes per lifecycle-phases.md.

Run with::

    uv run python examples/full_demo/server.py
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

import anyio

from openmcp import MCPServer, completion, get_context, prompt, resource, tool
from openmcp.server import NotificationFlags
from openmcp.types import (
    CompletionArgument,
    CompletionContext,
    CreateMessageRequestParams,
    CreateMessageResult,
    ElicitRequestParams,
    ElicitResult,
    PromptArgument,
    TextContent,
)

# Suppress logs for cleaner demo output
for logger_name in ("mcp", "httpx", "uvicorn", "uvicorn.access", "uvicorn.error"):
    logging.getLogger(logger_name).setLevel(logging.CRITICAL)


server = MCPServer(
    "full-demo",
    instructions="Demonstrates tools/resources/prompts/sampling/elicitation",
    notification_flags=NotificationFlags(prompts_changed=True, resources_changed=True, tools_changed=True),
)


with server.binding():

    @tool(description="Adds numbers")
    async def add(a: int, b: int) -> int:
        ctx = get_context()
        await ctx.debug("adding", data={"a": a, "b": b})
        async with ctx.progress(total=1) as tracker:
            await tracker.advance(1, message="computed")
        return a + b

    @tool(description="Sleeps for N seconds")
    async def sleep(seconds: float = 1.0) -> str:
        ctx = get_context()
        await ctx.info("sleep start", data={"seconds": seconds})
        async with ctx.progress(total=seconds) as tracker:
            remaining = seconds
            while remaining > 0:
                await anyio.sleep(1.0)
                remaining -= 1.0
                await tracker.advance(1.0, message=f"remaining {max(remaining, 0):.0f}s")
        return "slept"

    @resource("resource://time", mime_type="text/plain")
    def current_time() -> str:
        return datetime.utcnow().isoformat() + "Z"

    @prompt(
        name="plan-vacation",
        description="Guide the model through planning a vacation",
        arguments=[PromptArgument(name="destination", description="Where to travel", required=True)],
    )
    def plan_prompt(args: dict[str, str]) -> list[dict[str, str]]:
        destination = args.get("destination", "unknown")
        return [
            {"role": "assistant", "content": "You are a helpful planner. Use tools as needed."},
            {"role": "user", "content": f"Plan a trip to {destination}."},
        ]

    @completion(prompt="plan-vacation")
    async def plan_completion(argument: CompletionArgument, context: CompletionContext | None):
        """Provide synthetic completion for plan-vacation prompt."""
        return ["This is a synthetic completion."]


async def sampling_handler(ref: Any, params: CreateMessageRequestParams, context: Any) -> CreateMessageResult:
    """Handle sampling/createMessage requests."""
    return CreateMessageResult(content=[TextContent(type="text", text="Sampled by demo server")])


server.sampling.create_message = sampling_handler


async def elicitation_handler(ref: Any, params: ElicitRequestParams, context: Any) -> ElicitResult:
    """Handle elicitation/create requests."""
    return ElicitResult(fields={"confirm": True})


server.elicitation.create = elicitation_handler


async def main() -> None:
    """Serve the full-demo MCP server."""
    await server.serve(transport="streamable-http", verbose=False, log_level="critical", uvicorn_options={"access_log": False})


if __name__ == "__main__":
    asyncio.run(main())
