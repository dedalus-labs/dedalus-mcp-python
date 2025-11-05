# ==============================================================================
#                  © 2025 Dedalus Labs, Inc. and affiliates
#                            Licensed under MIT
#               github.com/dedalus-labs/openmcp-python/LICENSE
# ==============================================================================

"""Static resources with text and JSON content.

Demonstrates read-only data exposure via MCP resources: configuration files,
documentation, schemas, or any static text/JSON. Resources return str (wrapped
in TextResourceContents) or bytes (wrapped in BlobResourceContents).

Pattern:
- @resource(uri="...", mime_type="...") decorator
- Functions return str for text, bytes for binary
- URI scheme conventionalizes resource types (config://, doc://)
- Clients retrieve via resources/read

When to use:
- Static configuration data
- Documentation or help text
- Schema definitions, examples
- Read-only reference data

Spec: https://modelcontextprotocol.io/specification/2025-06-18/server/resources
Usage: uv run python examples/resources/static_resource.py
"""

from __future__ import annotations

import asyncio
import json
import logging

from openmcp import MCPServer, resource

# Suppress logs for clean demo output
for logger_name in ("mcp", "httpx", "uvicorn", "uvicorn.access", "uvicorn.error"):
    logging.getLogger(logger_name).setLevel(logging.CRITICAL)

server = MCPServer("static-resources")

with server.binding():

    @resource(
        uri="config://app/settings",
        name="Application Settings",
        description="Read-only application configuration",
        mime_type="application/json",
    )
    def app_settings() -> str:
        """Return configuration as JSON string.

        Resources can return str (text) or bytes (binary). When returning str,
        the server wraps it in TextResourceContents.
        """
        config = {
            "version": "1.0.0",
            "features": ["caching", "compression"],
            "limits": {"max_connections": 100, "timeout_seconds": 30},
        }
        return json.dumps(config, indent=2)

    @resource(
        uri="doc://readme",
        name="README",
        description="Project documentation",
        mime_type="text/markdown",
    )
    def readme() -> str:
        """Static text resource with Markdown content."""
        return """# Project Overview

This server demonstrates static resources in OpenMCP.

## Features
- Static configuration
- Documentation as resources
- Schema-based content
"""


async def main() -> None:
    await server.serve(transport="streamable-http", verbose=False, log_level="critical")


if __name__ == "__main__":
    asyncio.run(main())
