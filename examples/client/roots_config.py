# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Client advertising filesystem roots to MCP servers.

Demonstrates how to configure the roots capability to establish filesystem
boundaries for servers. The server can only access paths within these roots,
preventing directory traversal attacks.

Pattern:
1. Define initial Root objects with file:// URIs
2. Configure ClientCapabilitiesConfig with enable_roots=True and initial_roots
3. Use client.update_roots() to dynamically modify boundaries
4. Server receives roots/list_changed notifications

When to use this pattern:
- Sandboxing server filesystem access for security
- Multi-tenant systems where each client needs different boundaries
- Development environments requiring safe test isolation
- Production systems enforcing principle of least privilege

Spec: https://modelcontextprotocol.io/specification/2025-06-18/client/roots
See also: docs/dedalus_mcp/roots.md

Run with:
    uv run python examples/client/roots_config.py
"""

from __future__ import annotations

from pathlib import Path

import anyio

from dedalus_mcp.client import ClientCapabilitiesConfig, open_connection
from dedalus_mcp.types import Root


SERVER_URL = "http://127.0.0.1:8000/mcp"


async def main() -> None:
    """Connect to a server with filesystem roots configured."""
    project_root = Path.cwd()
    temp_dir = Path("/tmp")

    initial_roots = [
        Root(uri=project_root.as_uri(), name="Project Directory"),
        Root(uri=temp_dir.as_uri(), name="Temporary Files"),
    ]

    capabilities = ClientCapabilitiesConfig(
        enable_roots=True,
        initial_roots=initial_roots,
    )

    async with open_connection(
        url=SERVER_URL, transport="streamable-http", capabilities=capabilities
    ) as client:
        print("Connected with roots capability enabled")
        print(f"Server info: {client.initialize_result.serverInfo.name}")
        print("\nAdvertised roots:")
        for root in await client.list_roots():
            print(f"  - {root.name}: {root.uri}")

        # Demonstrate dynamic root updates
        await anyio.sleep(2)
        print("\nAdding new root...")

        new_roots = initial_roots + [Root(uri=Path.home().as_uri(), name="Home Directory")]
        await client.update_roots(new_roots, notify=True)

        print("Updated roots:")
        for root in await client.list_roots():
            print(f"  - {root.name}: {root.uri}")

        print("\nServer can now validate paths against these roots")
        await anyio.sleep(10)


if __name__ == "__main__":
    anyio.run(main)
