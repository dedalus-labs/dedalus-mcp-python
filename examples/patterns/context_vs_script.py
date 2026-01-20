# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Context manager vs script-style client usage.

Dedalus MCP supports two patterns for client lifecycle management:

1. Script-style (recommended for simple scripts):
   - Call MCPClient.connect() to get a client
   - Call client.close() when done
   - Explicit, clear control flow

2. Context manager (recommended for guaranteed cleanup):
   - Use `async with` to ensure cleanup on exceptions
   - Automatic resource management
   - Better for complex flows with multiple exit points

Both patterns are fully supported. Choose based on your needs.

Usage:
    # Start a server first:
    uv run python examples/showcase/01_minimal.py

    # Then run this:
    uv run python examples/patterns/context_vs_script.py
"""

import asyncio
import logging

from dedalus_mcp.client import MCPClient


for name in ("mcp", "httpx"):
    logging.getLogger(name).setLevel(logging.WARNING)

SERVER_URL = "http://127.0.0.1:8000/mcp"


# ============================================================================
# Pattern 1: Script-style (explicit close)
# ============================================================================


async def script_style_example() -> None:
    """Simple, explicit client usage."""
    print("\n--- Script Style ---")

    # Connect
    client = await MCPClient.connect(SERVER_URL)
    print(f"Connected to: {client.initialize_result.serverInfo.name}")

    # Use
    tools = await client.list_tools()
    print(f"Tools: {[t.name for t in tools.tools]}")

    result = await client.call_tool("add", {"a": 10, "b": 20})
    print(f"Result: {result.content[0].text}")

    # Close (important!)
    await client.close()
    print("Closed.")


# ============================================================================
# Pattern 2: Context manager (automatic cleanup)
# ============================================================================


async def context_manager_example() -> None:
    """Context manager for guaranteed cleanup."""
    print("\n--- Context Manager Style ---")

    async with await MCPClient.connect(SERVER_URL) as client:
        print(f"Connected to: {client.initialize_result.serverInfo.name}")

        tools = await client.list_tools()
        print(f"Tools: {[t.name for t in tools.tools]}")

        result = await client.call_tool("add", {"a": 100, "b": 200})
        print(f"Result: {result.content[0].text}")

    # Automatically closed when exiting the `async with` block
    print("Automatically closed.")


# ============================================================================
# Pattern 2b: Context manager with exception handling
# ============================================================================


async def context_manager_with_error() -> None:
    """Context manager cleans up even on exceptions."""
    print("\n--- Context Manager with Exception ---")

    try:
        async with await MCPClient.connect(SERVER_URL) as client:
            print(f"Connected to: {client.initialize_result.serverInfo.name}")

            # This will fail (tool doesn't exist)
            await client.call_tool("nonexistent_tool", {})

    except Exception as e:
        print(f"Error occurred: {type(e).__name__}: {e}")
        print("Client was still cleaned up properly!")


# ============================================================================
# When to use which?
# ============================================================================


async def main() -> None:
    print("=" * 50)
    print("Context Manager vs Script Style")
    print("=" * 50)

    # Script style: simple, explicit
    await script_style_example()

    # Context manager: automatic cleanup
    await context_manager_example()

    # Context manager: safe even with errors
    await context_manager_with_error()

    print("\n" + "=" * 50)
    print("When to use which?")
    print("=" * 50)
    print(
        """
Script Style (MCPClient.connect + close):
  ✓ Simple scripts and one-off operations
  ✓ When you want explicit control
  ✓ When cleanup timing matters
  ✓ Jupyter notebooks and REPLs

Context Manager (async with):
  ✓ Complex flows with multiple exit points
  ✓ When exceptions might occur
  ✓ Long-running applications
  ✓ When you want guaranteed cleanup

Both work. Both are correct. Pick what fits your code.
"""
    )


if __name__ == "__main__":
    asyncio.run(main())
