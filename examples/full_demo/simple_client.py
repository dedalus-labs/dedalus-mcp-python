# ==============================================================================
#                  © 2025 Dedalus Labs, Inc. and affiliates
#                            Licensed under MIT
#               github.com/dedalus-labs/openmcp-python/LICENSE
# ==============================================================================

"""Minimal MCP client for the Brave Search demo server.

Demonstrates low-level client request pattern using explicit request/response types
from openmcp.types. This approach provides maximum control and type safety for:

1. Protocol message construction (ClientRequest wrapping)
2. Response type validation (result type parameter)
3. Multiple sequential operations in one session

Follows the client lifecycle from docs/mcp/core/lifecycle/lifecycle-phases.md:
- Initialize connection
- List tools (tools/list per tools-list.md)
- Call tool (tools/call per tools-call.md)

Run after starting simple_server.py::

    uv run python examples/full_demo/simple_client.py
"""

from __future__ import annotations

import anyio

from openmcp.client import open_connection
from openmcp.types import CallToolRequest, CallToolRequestParams, CallToolResult, ClientRequest, ListToolsRequest, ListToolsResult

SERVER_URL: str = "http://127.0.0.1:8000/mcp"


async def main() -> None:
    """Connect to Brave Search server and exercise tool capabilities."""
    async with open_connection(url=SERVER_URL, transport="streamable-http") as client:
        # List tools (tools/list per tools-list.md)
        tools = await client.send_request(ClientRequest(ListToolsRequest()), ListToolsResult)
        print("Tools:", [tool.name for tool in tools.tools])

        # Call tool (tools/call per tools-call.md)
        result = await client.send_request(
            ClientRequest(
                CallToolRequest(
                    params=CallToolRequestParams(name="brave_web_search", arguments={"query": "model context protocol", "count": 1})
                )
            ),
            CallToolResult,
        )
        print("brave_web_search result:", result.content)


if __name__ == "__main__":
    anyio.run(main)
