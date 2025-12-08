# Copyright (c) 2025 Dedalus Labs, Inc.
# SPDX-License-Identifier: MIT

"""Minimal OpenMCP server example."""

from __future__ import annotations

import argparse
import asyncio
from dotenv import load_dotenv
from openmcp import MCPServer, tool

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
    """Start the OpenMCP server."""
    print("Serving on http://127.0.0.1:8000/mcp")
    await server.serve()


# --- Entry -------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Run the OpenMCP server")
    parser.add_argument("--server", action="store_true", help="Start server")
    args = parser.parse_args()

    if args.server:
        asyncio.run(run_server())
    else:
        print("Use --server to start.")


if __name__ == "__main__":
    main()