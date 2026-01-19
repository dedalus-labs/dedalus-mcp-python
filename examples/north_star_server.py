# Copyright (c) 2026 Dedalus Labs, Inc.
# SPDX-License-Identifier: MIT

"""Minimal Dedalus MCP server example."""

from __future__ import annotations

import argparse
import asyncio
from dotenv import load_dotenv
from dedalus_mcp import MCPServer, tool

load_dotenv()

# --- Tools -------------------------------------------------------------------


@tool(description="Add two numbers")
def add(a: int, b: int) -> int:
    return a + b


@tool(description="Multiply two numbers")
def multiply(a: int, b: int) -> int:
    return a * b


@tool(description="Return fake weather")
def get_weather(city: str) -> dict:
    return {"city": city, "temp": 72, "unit": "fahrenheit"}


# --- Server ------------------------------------------------------------------


server = MCPServer("demo")
server.collect(add, multiply, get_weather)


async def run_server():
    """Start the Dedalus MCP server."""
    print("Serving on http://127.0.0.1:8000/mcp")
    await server.serve()


# --- Entry -------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Run the Dedalus MCP server")
    parser.add_argument("--server", action="store_true", help="Start server")
    args = parser.parse_args()

    if args.server:
        asyncio.run(run_server())
    else:
        print("Use --server to start.")


if __name__ == "__main__":
    main()
