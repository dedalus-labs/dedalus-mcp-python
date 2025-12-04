# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Minimal MCP client demonstrating tool, resource, and prompt usage.

Demonstrates client-side capabilities per docs/mcp/core/lifecycle/lifecycle-phases.md:

1. Initialize connection (protocol handshake)
2. List capabilities (tools/list, resources/list, prompts/list)
3. Execute tool call (tools/call)
4. Read resource (resources/read)
5. Get prompt template (prompts/get)

Run after starting ``server.py`` in another shell::

    uv run python examples/hello_trip/client.py

Expected output: connection info, tool list, tool result, resource content, and prompt template.
"""

from __future__ import annotations

import asyncio

from dedalus_mcp import MCPClient
from dedalus_mcp.client import lambda_http_client


SERVER_URL = "http://127.0.0.1:8000/mcp"


async def main() -> None:
    """Connect to hello-trip server and exercise all capabilities."""
    async with (
        lambda_http_client(SERVER_URL, terminate_on_close=True) as (read_stream, write_stream, get_session_id),
        MCPClient(read_stream, write_stream) as client,
    ):
        # Protocol handshake per lifecycle-phases.md
        print("Connected. Protocol version:", client.initialize_result.protocolVersion)

        # List tools (tools/list per tools-list.md)
        tools = await client.session.list_tools()
        print("Tools:", [tool.name for tool in tools.tools])
        for tool_def in tools.tools:
            print("Tool schema:", tool_def.outputSchema)

        # Call tool (tools/call per tools-call.md)
        result = await client.session.call_tool("plan_trip", {"destination": "Barcelona", "days": 5, "budget": 2500})
        print("plan_trip result:", result.structuredContent or result.content)

        # List and read resources (resources-list.md, resources-read.md)
        resources = await client.session.list_resources()
        print("Resources:", [res.uri for res in resources.resources])

        resource_uri = str(resources.resources[0].uri) if resources.resources else None
        resource = await client.session.read_resource(resource_uri) if resource_uri else None
        if resource and resource.contents:
            print("Resource contents:", resource.contents[0].text)

        # Get prompt (prompts-get.md)
        prompt = await client.session.get_prompt("plan-vacation", {"destination": "Barcelona"})
        print("Prompt messages:", prompt.messages)


if __name__ == "__main__":
    asyncio.run(main())
