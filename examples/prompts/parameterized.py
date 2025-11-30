# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Dynamic prompts with required and optional parameter substitution.

Demonstrates parameterized prompts that accept runtime arguments to customize
message content. Arguments are declared in the decorator with required/optional
flags, and the framework validates them before function execution.

Pattern:
- Declare arguments in @prompt decorator with name, description, required flag
- Framework validates required arguments (missing -> INVALID_PARAMS error)
- Optional arguments support default values via dict.get()
- Functions receive validated arguments dict and return message templates

When to use:
- Dynamic prompt generation based on user inputs
- Reusable templates with customizable parameters
- Context-dependent system instructions
- Parameterized conversation starters (language, style, domain)

Spec: https://modelcontextprotocol.io/specification/2025-06-18/server/prompts
Reference: docs/mcp/spec/schema-reference/prompts-get.md
Usage: uv run python examples/prompts/parameterized.py
"""

from __future__ import annotations

import asyncio
import logging

from openmcp import MCPServer, prompt

# Suppress logs for clean demo output
for logger_name in ("mcp", "httpx", "uvicorn", "uvicorn.access", "uvicorn.error"):
    logging.getLogger(logger_name).setLevel(logging.CRITICAL)

server = MCPServer("parameterized-prompts")

with server.binding():

    @prompt(
        name="write-function",
        description="Generate a function with specified requirements",
        arguments=[
            {"name": "function_name", "description": "Function name", "required": True},
            {"name": "language", "description": "Language (default: python)", "required": False},
            {"name": "description", "description": "What it does", "required": True},
        ],
    )
    def write_function_prompt(arguments: dict[str, str] | None) -> list[dict[str, str]]:
        """Render prompt with runtime argument substitution.

        Framework validates required args before invocation. Missing required
        arguments trigger INVALID_PARAMS (-32602) automatically.
        """
        if not arguments:
            raise ValueError("Arguments required")

        func_name = arguments["function_name"]
        language = arguments.get("language", "python")  # Optional with default
        desc = arguments["description"]

        return [
            {"role": "assistant", "content": f"You are an expert {language} programmer."},
            {
                "role": "user",
                "content": f"Write a function named `{func_name}` that {desc}. "
                f"Follow {language} best practices and include type hints.",
            },
        ]


async def main() -> None:
    await server.serve(
        transport="streamable-http", verbose=False, log_level="critical", uvicorn_options={"access_log": False}
    )


if __name__ == "__main__":
    asyncio.run(main())
