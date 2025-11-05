# ==============================================================================
#                  © 2025 Dedalus Labs, Inc. and affiliates
#                            Licensed under MIT
#               github.com/dedalus-labs/openmcp-python/LICENSE
# ==============================================================================

"""Client implementing sampling capability for MCP servers.

Demonstrates how to handle sampling/createMessage requests from servers that
need LLM completions during tool execution. This example integrates with the
Anthropic API to provide real completions.

Pattern:
1. Define async handler accepting (context, CreateMessageRequestParams)
2. Convert MCP messages to provider format (Anthropic here)
3. Respect model preferences from params
4. Return CreateMessageResult or ErrorData

When to use this pattern:
- Servers need LLM completions during tool execution
- Multi-step reasoning workflows requiring delegation
- Agent-based architectures where servers consume LLM APIs
- Testing tool logic that depends on model responses

Spec: https://modelcontextprotocol.io/specification/2025-06-18/client/sampling
See also: docs/openmcp/sampling.md

Run with:
    export ANTHROPIC_API_KEY=your-key
    uv run python examples/client/sampling_handler.py
"""

from __future__ import annotations

import os

import anyio
import anthropic

from openmcp.client import ClientCapabilitiesConfig, open_connection
from openmcp.types import (
    CreateMessageRequestParams,
    CreateMessageResult,
    ErrorData,
    Role,
    StopReason,
    TextContent,
)


SERVER_URL = "http://127.0.0.1:8000/mcp"


async def sampling_handler(
    _context: object, params: CreateMessageRequestParams
) -> CreateMessageResult | ErrorData:
    """Handle sampling/createMessage requests by invoking Anthropic API."""
    try:
        client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

        messages = [
            {
                "role": msg.role,
                "content": msg.content.text if hasattr(msg.content, "text") else str(msg.content),
            }
            for msg in params.messages
        ]

        model = "claude-3-5-sonnet-20241022"
        if params.modelPreferences and params.modelPreferences.hints:
            model = params.modelPreferences.hints[0].name

        response = await client.messages.create(
            model=model, messages=messages, max_tokens=params.maxTokens or 1024
        )

        text_content = response.content[0].text if response.content else ""
        return CreateMessageResult(
            model=response.model,
            content=TextContent(type="text", text=text_content),
            role=Role.assistant,
            stopReason=(
                StopReason.endTurn if response.stop_reason == "end_turn" else StopReason.maxTokens
            ),
        )

    except Exception as e:
        return ErrorData(code=-32603, message=f"Sampling failed: {e}")


async def main() -> None:
    """Connect to a server that uses sampling and handle its requests."""
    capabilities = ClientCapabilitiesConfig(sampling=sampling_handler)

    async with open_connection(
        url=SERVER_URL, transport="streamable-http", capabilities=capabilities
    ) as client:
        print("Connected with sampling capability enabled")
        print(f"Server info: {client.initialize_result.serverInfo.name}")
        await anyio.sleep(60)


if __name__ == "__main__":
    anyio.run(main)
