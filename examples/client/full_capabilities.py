# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Client with all capabilities enabled.

Demonstrates a fully-featured MCP client that advertises all optional
capabilities: sampling, elicitation, roots, and logging.

Pattern: Combine multiple capability handlers in ClientCapabilitiesConfig.

Spec: https://modelcontextprotocol.io/specification/2025-06-18/

Run: export ANTHROPIC_API_KEY=your-key && uv run python examples/client/full_capabilities.py
"""

from __future__ import annotations

import os
from pathlib import Path

import anyio
import anthropic

from dedalus_mcp.client import ClientCapabilitiesConfig, open_connection
from dedalus_mcp.types import (
    ClientRequest,
    CreateMessageRequestParams,
    CreateMessageResult,
    ElicitRequestParams,
    ElicitResult,
    ErrorData,
    ListToolsRequest,
    ListToolsResult,
    LoggingMessageNotificationParams,
    Role,
    Root,
    StopReason,
    TextContent,
)


SERVER_URL = "http://127.0.0.1:8000/mcp"


async def sampling_handler(
    _context: object, params: CreateMessageRequestParams
) -> CreateMessageResult | ErrorData:
    """Handle sampling requests with Anthropic API."""
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

        return CreateMessageResult(
            model=response.model,
            content=TextContent(type="text", text=response.content[0].text),
            role=Role.assistant,
            stopReason=StopReason.endTurn,
        )
    except Exception as e:
        return ErrorData(code=-32603, message=f"Sampling failed: {e}")


async def elicitation_handler(
    _context: object, params: ElicitRequestParams
) -> ElicitResult | ErrorData:
    """Handle elicitation requests via CLI prompts (auto-accepts for demo)."""
    try:
        print(f"\n{'=' * 60}\nServer requests: {params.message}\n{'=' * 60}\n")
        properties = params.requestedSchema.get("properties", {})
        content: dict[str, object] = {}
        for field_name, field_schema in properties.items():
            field_type = field_schema.get("type", "string")
            content[field_name] = (
                True
                if field_type == "boolean"
                else 42 if field_type in ("integer", "number") else "demo-value"
            )
        return ElicitResult(action="accept", content=content)
    except Exception as e:
        return ErrorData(code=-32603, message=f"Elicitation failed: {e}")


def logging_handler(params: LoggingMessageNotificationParams) -> None:
    """Handle logging notifications from server."""
    level = params.level.upper() if params.level else "INFO"
    print(f"[SERVER {level}] {params.data or params.logger}")


async def main() -> None:
    """Connect with all client capabilities enabled."""
    initial_roots = [
        Root(uri=Path.cwd().as_uri(), name="Working Directory"),
        Root(uri=Path("/tmp").as_uri(), name="Temp"),
    ]
    capabilities = ClientCapabilitiesConfig(
        sampling=sampling_handler,
        elicitation=elicitation_handler,
        logging=logging_handler,
        enable_roots=True,
        initial_roots=initial_roots,
    )

    async with open_connection(
        url=SERVER_URL, transport="streamable-http", capabilities=capabilities
    ) as client:
        init = client.initialize_result
        print(f"Connected with all capabilities enabled")
        print(f"Server: {init.serverInfo.name} | Protocol: {init.protocolVersion}")

        caps = init.capabilities
        print("\nClient capabilities:")
        if hasattr(caps, "sampling") and caps.sampling:
            print("  - sampling: enabled")
        if hasattr(caps, "elicitation") and caps.elicitation:
            print("  - elicitation: enabled")
        if hasattr(caps, "roots") and caps.roots:
            print("  - roots: enabled")
            for root in await client.list_roots():
                print(f"    - {root.name}: {root.uri}")

        tools = (await client.send_request(ClientRequest(ListToolsRequest()), ListToolsResult)).tools
        print(f"\nAvailable tools: {len(tools)}")
        for tool in tools[:5]:
            print(f"  - {tool.name}: {tool.description or 'no description'}")

        print("\nClient ready. Server can now use all advertised capabilities.")
        await anyio.sleep(30)


if __name__ == "__main__":
    anyio.run(main)
