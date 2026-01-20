# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Client that handles user input requests from the server.

When the server calls `server.request_elicitation()`, this client
receives the request and presents it to the user (or auto-responds
for testing).

Usage:
    # Terminal 1:
    uv run python examples/capabilities/elicitation/server.py

    # Terminal 2:
    uv run python examples/capabilities/elicitation/client.py
"""

import asyncio
import logging

from dedalus_mcp.client import ClientCapabilitiesConfig, MCPClient
from dedalus_mcp.types import ElicitResult


for name in ("mcp", "httpx"):
    logging.getLogger(name).setLevel(logging.WARNING)


# ============================================================================
# Elicitation Handler
# ============================================================================


async def elicitation_handler(context, params) -> ElicitResult:
    """Handle elicitation requests from the server.

    In a real application, you'd present this to the user via:
    - CLI prompt
    - GUI dialog
    - Web form
    - Slack/Discord message
    """
    print(f"\n{'=' * 50}")
    print("USER INPUT REQUESTED")
    print(f"{'=' * 50}")
    print(f"Message: {params.message}")
    print(f"Schema: {params.requestedSchema}")
    print(f"{'=' * 50}")

    # For this demo, auto-respond based on the schema
    schema = params.requestedSchema or {}
    properties = schema.get("properties", {})

    response_content = {}

    # Auto-fill based on property names (demo only!)
    for prop_name, prop_schema in properties.items():
        prop_type = prop_schema.get("type")

        if prop_name in ("confirmed", "approved"):
            # Auto-approve for demo
            response_content[prop_name] = True
            print(f"[Auto] {prop_name} = True")

        elif prop_name == "display_name":
            response_content[prop_name] = "Demo User"
            print(f"[Auto] {prop_name} = 'Demo User'")

        elif prop_name == "role":
            response_content[prop_name] = "developer"
            print(f"[Auto] {prop_name} = 'developer'")

        elif prop_name == "reason":
            response_content[prop_name] = "Automated approval for demo"
            print(f"[Auto] {prop_name} = 'Automated approval for demo'")

        elif prop_type == "boolean":
            response_content[prop_name] = prop_schema.get("default", False)
            print(f"[Auto] {prop_name} = {response_content[prop_name]}")

        elif prop_type == "string":
            response_content[prop_name] = f"demo_{prop_name}"
            print(f"[Auto] {prop_name} = 'demo_{prop_name}'")

    print(f"{'=' * 50}\n")

    return ElicitResult(action="accept", content=response_content)


# ============================================================================
# Main
# ============================================================================


async def main() -> None:
    config = ClientCapabilitiesConfig(elicitation=elicitation_handler)

    print("Connecting to elicitation demo server...")
    client = await MCPClient.connect("http://127.0.0.1:8000/mcp", capabilities=config)

    print(f"Connected to: {client.initialize_result.serverInfo.name}")
    print("This client handles user input requests from the server.\n")

    # Demo 1: Confirmation dialog
    print("=" * 50)
    print("Demo 1: Delete File (Confirmation)")
    print("=" * 50)

    result = await client.call_tool("delete_file", {"path": "/tmp/important.txt"})
    print(f"Result: {result.structuredContent}\n")

    # Demo 2: Form input
    print("=" * 50)
    print("Demo 2: Create Account (Form Input)")
    print("=" * 50)

    result = await client.call_tool("create_account", {"email": "demo@example.com"})
    print(f"Result: {result.structuredContent}\n")

    # Demo 3: Approval workflow
    print("=" * 50)
    print("Demo 3: Deploy (Approval Workflow)")
    print("=" * 50)

    result = await client.call_tool("deploy", {"environment": "production", "version": "v2.0.0"})
    print(f"Result: {result.structuredContent}\n")

    await client.close()
    print("Demo complete!")


if __name__ == "__main__":
    asyncio.run(main())
