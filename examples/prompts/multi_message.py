# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Multi-turn conversations with typed message content.

Demonstrates complex prompt patterns using explicit type constructors for
fine-grained control over message structure. Returns GetPromptResult with
fully-typed PromptMessage and TextContent objects for multi-turn flows.

Pattern:
- Return GetPromptResult directly (vs list[dict] auto-conversion)
- Construct PromptMessage objects with explicit role and content
- Use TextContent for typed text blocks (supports future content types)
- Build sequential message flows (context -> examples -> query)

When to use:
- Multi-turn conversation templates
- Complex debugging or analysis workflows
- Structured prompt sequences (system -> context -> task)
- Type-safe message construction

Spec: https://modelcontextprotocol.io/specification/2025-06-18/server/prompts
Reference: docs/mcp/spec/schema-reference/prompts-get.md
Usage: uv run python examples/prompts/multi_message.py
"""

from __future__ import annotations

import asyncio
import logging

from openmcp import MCPServer, prompt
from openmcp.types import GetPromptResult, PromptMessage, TextContent

# Suppress logs for clean demo output
for logger_name in ("mcp", "httpx", "uvicorn", "uvicorn.access", "uvicorn.error"):
    logging.getLogger(logger_name).setLevel(logging.CRITICAL)

server = MCPServer("multi-message-prompts")

with server.binding():

    @prompt(
        name="debug-session",
        description="Guide a debugging session with context and examples",
        arguments=[{"name": "error_message", "required": True}, {"name": "code_snippet", "required": True}],
    )
    def debug_session_prompt(arguments: dict[str, str] | None) -> GetPromptResult:
        """Return fully-typed multi-turn conversation template.

        Uses explicit type constructors (PromptMessage, TextContent) for
        structured message sequences. Alternative to list[dict] shorthand.
        """
        if not arguments:
            raise ValueError("Arguments required")

        error_msg = arguments["error_message"]
        code = arguments["code_snippet"]

        messages = [
            PromptMessage(
                role="assistant",
                content=TextContent(
                    type="text",
                    text="You are a debugging assistant. Analyze errors methodically: "
                    "1) Identify root cause, 2) Explain why, 3) Suggest fix.",
                ),
            ),
            PromptMessage(role="user", content=TextContent(type="text", text=f"Error:\n```\n{error_msg}\n```")),
            PromptMessage(
                role="user", content=TextContent(type="text", text=f"Code:\n```\n{code}\n```\n\nWhat's wrong?")
            ),
        ]

        return GetPromptResult(description="Debugging session for error analysis", messages=messages)


async def main() -> None:
    await server.serve(
        transport="streamable-http", verbose=False, log_level="critical", uvicorn_options={"access_log": False}
    )


if __name__ == "__main__":
    asyncio.run(main())
