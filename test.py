"""Canonical OpenMCP server entrypoint used for manual testing.

Run with:

    PYTHONPATH=src uv run --python 3.12 test.py

This script showcases the ambient registration pattern and emits basic log
messages for lifecycle events.
"""

from __future__ import annotations

import asyncio

from openmcp import MCPServer, tool
from openmcp.utils import configure_logging, get_logger


configure_logging()
log = get_logger(__name__)


server = MCPServer(
    "demo",
    instructions="Example MCP server",
    transport="streamable-http",
)


with server.collecting():
    @tool(description="Adds two numbers")
    def add(a: int, b: int) -> int:
        log.info("add(%s, %s) invoked", a, b)
        return a + b

    @tool(description="Echo text back to the caller")
    def echo(text: str) -> str:
        log.info("echo(%r) invoked", text)
        return text


async def main() -> None:
    log.info("Starting OpenMCP server on STDIO with tools: %s", server.tool_names)
    try:
        await server.serve()
    except Exception:
        log.exception("Server exited with an unexpected error")
        raise
    else:
        log.info("Server shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
