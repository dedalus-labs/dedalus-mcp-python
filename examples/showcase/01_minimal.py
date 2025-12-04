# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Minimal MCP server in 15 lines.

The absolute smallest working MCP server. One tool, automatic schema
inference, streamable HTTP transport. Start here.

Usage:
    uv run python examples/showcase/01_minimal.py
    # Server runs at http://127.0.0.1:8000/mcp
"""

import asyncio
from dedalus_mcp import MCPServer, tool

server = MCPServer("minimal")


@tool(description="Add two numbers")
def add(a: int, b: int) -> int:
    return a + b


server.collect(add)

if __name__ == "__main__":
    asyncio.run(server.serve())
