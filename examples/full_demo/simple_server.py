# ==============================================================================
#                  © 2025 Dedalus Labs, Inc. and affiliates
#                            Licensed under MIT
#               github.com/dedalus-labs/openmcp-python/LICENSE
# ==============================================================================

"""Minimal Brave Search MCP server.

Demonstrates external tool registration pattern where tools are defined in a
separate module and registered via function call. This pattern enables:

- Clean separation between server setup and tool definitions
- Reusable tool libraries across multiple servers
- Conditional tool registration based on environment/config

Follows tools/list and tools/call specs from docs/mcp/spec/schema-reference/tools-*.md.

Requires:
    BRAVE_API_KEY environment variable (from .env file)

Run with::

    uv run python examples/full_demo/simple_server.py
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from openmcp import MCPServer

# Suppress logs for cleaner demo output
for logger_name in ("mcp", "httpx", "uvicorn", "uvicorn.access", "uvicorn.error"):
    logging.getLogger(logger_name).setLevel(logging.CRITICAL)

THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

from simple_tools import register_brave_tools  # noqa: E402

load_dotenv()

server = MCPServer("brave-search", instructions="Brave Search tools")

register_brave_tools(server, api_key=os.getenv("BRAVE_API_KEY"))


async def main() -> None:
    """Serve the Brave Search MCP server."""
    await server.serve(transport="streamable-http", verbose=False, log_level="critical", uvicorn_options={"access_log": False})


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
