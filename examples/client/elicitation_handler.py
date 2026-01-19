# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Client implementing elicitation capability for MCP servers.

Demonstrates how to handle elicitation/create requests from servers that need
user input during tool execution. This example uses simple CLI prompts but
could be adapted for GUI dialogs, web forms, etc.

Pattern:
1. Define async handler accepting (context, ElicitRequestParams)
2. Parse requestedSchema to understand required fields
3. Collect user input matching schema types
4. Return ElicitResult with action (accept/decline/cancel) and content

When to use this pattern:
- Tools requiring user confirmation (delete operations, payments)
- Dynamic form collection during execution
- Multi-step workflows with human-in-the-loop
- Permission elevation requests

Spec: https://modelcontextprotocol.io/specification/2025-06-18/client/elicitation
See also: docs/dedalus_mcp/elicitation.md

Run with:
    uv run python examples/client/elicitation_handler.py
"""

from __future__ import annotations

import anyio

from dedalus_mcp.client import ClientCapabilitiesConfig, open_connection
from dedalus_mcp.types import (
    CallToolRequest,
    CallToolRequestParams,
    CallToolResult,
    ClientRequest,
    ElicitRequestParams,
    ElicitResult,
    ErrorData,
)


SERVER_URL = "http://127.0.0.1:8000/mcp"


async def elicitation_handler(_context: object, params: ElicitRequestParams) -> ElicitResult | ErrorData:
    """Handle elicitation/create requests by prompting the user via CLI."""
    try:
        print(f"\n{'=' * 60}")
        print(f"Server requests input: {params.message}")
        print(f"{'=' * 60}\n")

        schema = params.requestedSchema
        properties = schema.get("properties", {})
        required = schema.get("required", [])

        content: dict[str, object] = {}
        for field_name, field_schema in properties.items():
            field_type = field_schema.get("type", "string")
            is_required = field_name in required

            prompt = f"{field_name} ({field_type})"
            if not is_required:
                prompt += " [optional]"
            prompt += ": "

            while True:
                try:
                    user_input = await anyio.to_thread.run_sync(input, prompt)

                    if not user_input:
                        if is_required:
                            print(f"  Error: {field_name} is required")
                            continue
                        break

                    if field_type == "boolean":
                        content[field_name] = user_input.lower() in ("true", "yes", "1", "y")
                    elif field_type == "integer":
                        content[field_name] = int(user_input)
                    elif field_type == "number":
                        content[field_name] = float(user_input)
                    else:
                        content[field_name] = user_input

                    break

                except ValueError:
                    print(f"  Error: Expected {field_type}, try again")

        confirm = await anyio.to_thread.run_sync(input, "\nSubmit? [Y/n/cancel]: ")

        if confirm.lower() == "cancel":
            return ElicitResult(action="cancel", content={})
        elif confirm.lower() == "n":
            return ElicitResult(action="decline", content={})
        else:
            return ElicitResult(action="accept", content=content)

    except Exception as e:
        return ErrorData(code=-32603, message=f"Elicitation failed: {e}")


async def main() -> None:
    """Connect to a server that uses elicitation and handle its requests."""
    capabilities = ClientCapabilitiesConfig(elicitation=elicitation_handler)

    async with open_connection(url=SERVER_URL, transport="streamable-http", capabilities=capabilities) as client:
        print("Connected with elicitation capability enabled")
        print(f"Server info: {client.initialize_result.serverInfo.name}")

        try:
            result = await client.send_request(
                ClientRequest(
                    CallToolRequest(params=CallToolRequestParams(name="some_tool_needing_confirmation", arguments={}))
                ),
                CallToolResult,
            )
            print(f"\nTool result: {result.content}")
        except Exception as e:
            print(f"\nError calling tool: {e}")


if __name__ == "__main__":
    anyio.run(main)
