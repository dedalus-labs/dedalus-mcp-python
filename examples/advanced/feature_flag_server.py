"""Feature-flagged tool exposure using dynamic mode.

Demonstrates runtime tool registration/unregistration based on feature flags.
Dynamic behavior requires allow_dynamic_tools=True and callers MUST emit
notifications/tools/list_changed after each mutation.

Pattern:
1. Create server with allow_dynamic_tools=True
2. Use server.binding() to register/unregister tools
3. Call server.notify_tools_list_changed() after mutations
4. Clients receive tools/list_changed notifications

When to use this pattern:
- A/B testing with gradual feature rollout
- Kill switches for unstable features
- Environment-specific tool exposure
- Multi-tenant feature gating

Reference:
    - Dynamic tools: docs/mcp/spec/schema-reference/tools-list.md
    - Notifications: docs/mcp/spec/schema-reference/notifications.md
"""

from __future__ import annotations

import asyncio
import logging

from openmcp import MCPServer, tool

# Suppress SDK and server logs for cleaner demo output
for logger_name in ("mcp", "httpx", "uvicorn", "uvicorn.access", "uvicorn.error"):
    logging.getLogger(logger_name).setLevel(logging.CRITICAL)


server = MCPServer("feature-flagged", allow_dynamic_tools=True)
_flag_enabled = False


def bootstrap() -> MCPServer:
    """Register the baseline tool set."""
    with server.binding():

        @tool(description="Ping the server")
        def ping() -> str:
            return "pong"

    return server


async def set_feature(*, enabled: bool = False) -> None:
    """Toggle the experimental search tool at runtime."""
    global _flag_enabled
    _flag_enabled = enabled

    with server.binding():

        @tool(description="Ping the server")
        def ping() -> str:
            return "pong"

        if _flag_enabled:

            @tool(description="Experimental semantic search")
            async def search(query: str) -> str:
                return f"results for {query}"

    await server.notify_tools_list_changed()


async def main() -> None:
    """Launch the server in STDIO mode for development."""
    bootstrap()
    print("Serving feature-flagged tools. Toggle via: await set_feature(enabled=True|False)")
    async with asyncio.TaskGroup() as tg:
        tg.create_task(server.serve_stdio(validate=False))


if __name__ == "__main__":
    asyncio.run(main())


__all__ = ["bootstrap", "server", "set_feature"]
