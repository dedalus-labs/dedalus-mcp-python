# ==============================================================================
#                  © 2025 Dedalus Labs, Inc. and affiliates
#                            Licensed under MIT
#               github.com/dedalus-labs/openmcp-python/LICENSE
# ==============================================================================

"""Client-side request cancellation demonstration.

Shows how to cancel a long-running tool call from the client side using MCP's
cancellation primitive. The client sends a `notifications/cancelled` message
with the request ID, allowing the server to abort in-progress operations.

Pattern:
1. Client initiates a tool call (e.g., long-running `sleep` operation)
2. Client sends cancellation notification after timeout
3. Server receives cancellation and stops execution
4. Client task group is cancelled to prevent hanging

Key APIs:
- `client.send_request()` - Initiates async tool call
- `client.cancel_request(request_id, reason)` - Sends cancellation notification
- `tg.cancel_scope.cancel()` - Aborts client-side waiting

See spec details at:
https://spec.modelcontextprotocol.io/specification/2025-11-05/basic/cancellation

Prerequisites:
    Requires `examples/full_demo/server.py` to be running with a `sleep` tool.

Usage:
    # Terminal 1: Start the server
    python examples/full_demo/server.py

    # Terminal 2: Run cancellation demo
    python examples/cancellation.py
"""

from __future__ import annotations

import anyio
from mcp.client.streamable_http import streamablehttp_client

from openmcp import MCPClient
from openmcp.types import CallToolRequest, CallToolResult, ClientRequest


async def main() -> None:
    """Invoke a long-running tool, then cancel it after 2 seconds."""
    async with streamablehttp_client("http://127.0.0.1:8000/mcp") as (reader, writer, _):
        async with MCPClient(reader, writer) as client:
            request = ClientRequest(CallToolRequest(name="sleep", arguments={"seconds": 10}))

            async def invoke() -> CallToolResult:
                return await client.send_request(request, CallToolResult)

            async with anyio.create_task_group() as tg:
                tg.start_soon(invoke)
                await anyio.sleep(2)
                await client.cancel_request(request.id, reason="timeout")
                tg.cancel_scope.cancel()
                print("Cancellation sent")


if __name__ == "__main__":
    anyio.run(main)
