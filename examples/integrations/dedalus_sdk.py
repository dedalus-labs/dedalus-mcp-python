# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Passing Dedalus MCP servers directly to the Dedalus SDK.

Demonstrates the Protocol pattern: the SDK accepts MCPServerLike objects
without importing dedalus_mcp. Python's structural typing makes this work.

Usage:
    uv run python examples/integrations/dedalus_sdk.py --server  # Process 1
    uv run python examples/integrations/dedalus_sdk.py --client  # Process 2
"""

from __future__ import annotations

import argparse
import asyncio
import os

from dotenv import load_dotenv

from dedalus_mcp import MCPServer, tool


load_dotenv()


# --- Dedalus MCP Server ----------------------------------------------------------


@tool(description="Add two numbers together")
def add(a: int, b: int) -> int:
    return a + b


@tool(description="Multiply two numbers together")
def multiply(a: int, b: int) -> int:
    return a * b


@tool(description="Get the current weather for a city")
def get_weather(city: str) -> dict:
    return {"city": city, "temperature": 72, "unit": "fahrenheit", "conditions": "sunny"}


server = MCPServer("demo-calculator")
server.collect(add, multiply, get_weather)


# --- Server Mode -------------------------------------------------------------


async def run_server():
    """Start the Dedalus MCP server."""
    print("Starting Dedalus MCP server on http://127.0.0.1:8000/mcp")
    print("Tools available: add, multiply, get_weather")
    await server.serve()


# --- Client Mode -------------------------------------------------------------


async def run_client():
    """Use the server with Dedalus SDK via mcp_servers parameter."""
    try:
        from dedalus_labs import AsyncDedalus
        from dedalus_labs.lib.runner import DedalusRunner
    except ImportError:
        print("Error: dedalus_labs not installed. Run: uv add dedalus_labs")
        return

    if not os.getenv("DEDALUS_API_KEY"):
        print("Error: DEDALUS_API_KEY not set.")
        return

    client = AsyncDedalus(base_url="http://localhost:8080")
    runner = DedalusRunner(client, verbose=True)

    print("\n" + "=" * 60)
    print("Dedalus SDK + Dedalus MCP Integration Demo")
    print("=" * 60)

    # Two ways to pass MCP servers:
    #
    # 1. Server object (same process): If you call `await server.serve()` in THIS
    #    process and then pass the server object, it has a URL and works directly.
    #
    # 2. URL string (separate process): If the server runs in another process
    #    (like this example), pass the URL string instead.
    #
    server_url = "http://127.0.0.1:8000/mcp"
    print(f"\nConnecting to MCP server at {server_url}...")

    result = await runner.run(
        input="What is 15 + 27? Also, what's the weather in San Francisco?",
        model="openai/gpt-4o-mini",
        mcp_servers=[server_url],
        stream=False,
    )

    print("\n" + "=" * 60)
    print("Result:")
    print("=" * 60)
    print(result.final_output)
    print(f"\nTools called: {result.tools_called}")
    print(f"Steps used: {result.steps_used}")


# --- Protocol Demo -----------------------------------------------------------


def demonstrate_protocol():
    """Show how the Protocol pattern works."""
    from dedalus_labs.lib.runner.protocols import MCPServerProtocol, is_mcp_server

    print("\n" + "=" * 60)
    print("Protocol Pattern Demonstration")
    print("=" * 60)

    print(f"\nDedalus MCP server: {server}")
    print(f"  server.name = {server.name!r}")
    print(f"  server.url = {server.url!r}")
    print(f"  is_mcp_server(server) = {is_mcp_server(server)}")
    print(f"  isinstance(server, MCPServerProtocol) = {isinstance(server, MCPServerProtocol)}")

    print("\nRemote slug: 'windsor/brave-search-mcp'")
    print(f"  is_mcp_server('windsor/brave-search-mcp') = {is_mcp_server('windsor/brave-search-mcp')}")

    # Minimal fake server
    class MinimalServer:
        name = "minimal"
        url = "http://localhost:9000/mcp"

        def serve(self):
            pass

    print("\nMinimal fake server:")
    print(f"  isinstance(MinimalServer(), MCPServerProtocol) = {isinstance(MinimalServer(), MCPServerProtocol)}")

    print("\n✓ Protocol pattern allows SDK to accept Dedalus MCP servers")
    print("  without importing dedalus_mcp at all!")


# --- Wire Format Demo --------------------------------------------------------


def demonstrate_wire_format():
    """Show how MCP servers are serialized for API transmission.

    Identity resolution is handled by the MCP Router (mcp.dedaluslabs.ai):
    - Slugs: looked up in marketplace registry
    - Dedalus URLs: identity from URL path (org_slug/path_token)
    - Localhost URLs: associated with caller's org via API key

    No extra metadata needed in the wire format.
    """
    import json

    from dedalus_labs.lib.runner.mcp_wire import MCPServerWireSpec, serialize_mcp_servers

    print("\n" + "=" * 60)
    print("Wire Format Demonstration")
    print("=" * 60)

    # Simulate running server
    server._serving_url = "http://127.0.0.1:8000/mcp"

    print("\n1. Slug-based server (marketplace)")
    print("-" * 40)
    spec = MCPServerWireSpec.from_slug("dedalus-labs/brave-search", version="v1.0.0")
    print(f"Wire format: {json.dumps(spec.to_wire(), indent=2)}")

    print("\n2. URL-based server (local dev)")
    print("-" * 40)
    spec = MCPServerWireSpec.from_url("http://127.0.0.1:8000/mcp")
    print(f"Wire format: {json.dumps(spec.to_wire(), indent=2)}")

    print("\n3. Mixed mcp_servers serialization")
    print("-" * 40)
    wire_data = serialize_mcp_servers([server, "dedalus-labs/brave-search", "dedalus-labs/weather@v2"])
    print(f"Output: {json.dumps(wire_data, indent=2)}")

    print("\n4. Full API payload")
    print("-" * 40)
    payload = {
        "model": "openai/gpt-4o-mini",
        "messages": [{"role": "user", "content": "What is 2 + 2?"}],
        "mcp_servers": wire_data,
    }
    print(json.dumps(payload, indent=2))

    server._serving_url = None

    print("\n✓ Clean wire format (no extra metadata)")
    print("✓ Router handles identity via URL structure")
    print("✓ Efficient (slugs serialize to plain strings)")


# --- Entry Point -------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Dedalus MCP + Dedalus SDK Integration")
    parser.add_argument("--server", action="store_true", help="Run as MCP server")
    parser.add_argument("--client", action="store_true", help="Run as SDK client")
    parser.add_argument("--demo", action="store_true", help="Demonstrate Protocol pattern")
    parser.add_argument("--wire", action="store_true", help="Demonstrate wire format")
    args = parser.parse_args()

    if args.server:
        asyncio.run(run_server())
    elif args.client:
        asyncio.run(run_client())
    elif args.demo:
        demonstrate_protocol()
    elif args.wire:
        demonstrate_wire_format()
    else:
        print("Usage:")
        print("  --server  Start the Dedalus MCP server")
        print("  --client  Use the server with Dedalus SDK")
        print("  --demo    Demonstrate Protocol pattern")
        print("  --wire    Demonstrate wire format")
        print("\nExample:")
        print("  Terminal 1: uv run python examples/integrations/dedalus_sdk.py --server")
        print("  Terminal 2: uv run python examples/integrations/dedalus_sdk.py --client")


if __name__ == "__main__":
    main()
