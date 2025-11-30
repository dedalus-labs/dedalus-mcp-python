# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Static prompt templates with fixed message sequences.

Demonstrates the simplest prompt registration pattern: static message templates
that guide model behavior without runtime parameters. Prompts define reusable
conversation starters that clients can invoke via prompts/get.

Pattern:
- @prompt decorator registers prompt by name
- Functions return list[dict] (auto-converted to PromptMessage objects)
- No parameters required—templates are static
- Messages define role-based conversation sequences

When to use:
- Standard conversation templates (code review, debugging, analysis)
- Fixed system instructions or personas
- Reusable conversation patterns across sessions
- Boilerplate reduction for common model interactions

Spec: https://modelcontextprotocol.io/specification/2025-06-18/server/prompts
Reference: docs/mcp/spec/schema-reference/prompts-get.md
Usage: uv run python examples/prompts/basic_prompt.py
"""

from __future__ import annotations

import asyncio
import logging

from openmcp import MCPServer, prompt

# Suppress logs for clean demo output
for logger_name in ("mcp", "httpx", "uvicorn", "uvicorn.access", "uvicorn.error"):
    logging.getLogger(logger_name).setLevel(logging.CRITICAL)

server = MCPServer("basic-prompts")

with server.binding():

    @prompt(
        name="code-review",
        description="Guide the model through a code review process",
    )
    def code_review_prompt(arguments: dict[str, str] | None) -> list[dict[str, str]]:
        """Static code review template.

        Returns list[dict] which framework converts to PromptMessage objects.
        Each dict must have 'role' and 'content' keys.
        """
        return [
            {
                "role": "assistant",
                "content": "You are a careful code reviewer focusing on correctness, readability, and maintainability.",
            },
            {"role": "user", "content": "Review the code and provide constructive feedback."},
        ]


async def main() -> None:
    await server.serve(
        transport="streamable-http",
        verbose=False,
        log_level="critical",
        uvicorn_options={"access_log": False},
    )


if __name__ == "__main__":
    asyncio.run(main())
