# ==============================================================================
#                  © 2025 Dedalus Labs, Inc. and affiliates
#                            Licensed under MIT
#               github.com/dedalus-labs/openmcp-python/LICENSE
# ==============================================================================

"""Utility helpers for registering Brave Search tools in the demo server.

Demonstrates the reusable tool library pattern where tools are:

1. Defined as decorated functions within a registration context
2. Parameterized by external dependencies (API client)
3. Tagged for discovery and filtering (per tools/list spec)

Each tool follows the tools/call specification from
docs/mcp/spec/schema-reference/tools-call.md, accepting structured arguments
and returning JSON-serializable results.

Usage::

    server = MCPServer("my-server")
    register_brave_tools(server, api_key="...")
"""

from __future__ import annotations

from typing import Any

from brave_search_python_client import (
    BraveSearch,
    ImagesSearchRequest,
    NewsSearchRequest,
    VideosSearchRequest,
    WebSearchRequest,
)

from openmcp import tool
from openmcp.server import MCPServer

__all__ = ["register_brave_tools"]


def _serialise(result: Any) -> Any:
    """Return a JSON-serializable representation of Brave responses."""
    if hasattr(result, "model_dump"):
        return result.model_dump()
    if hasattr(result, "dict"):
        return result.dict()
    return result


def register_brave_tools(server: MCPServer, *, api_key: str | None = None) -> None:
    """Register Brave Search tools onto *server*.

    Args:
        server: The MCPServer instance to register tools on
        api_key: Brave Search API key (required)

    Raises:
        ValueError: If api_key is None
    """
    if api_key is None:
        raise ValueError("BRAVE_SEARCH_API_KEY not set; unable to configure Brave tools")

    client = BraveSearch(api_key=api_key)

    with server.binding():

        @tool(tags=["search", "web"])
        async def brave_web_search(query: str, count: int = 5) -> Any:
            """Run a Brave web search and return the raw payload."""
            request = WebSearchRequest(q=query, count=count)
            response = await client.web(request)
            return _serialise(response)

        @tool(tags=["search", "images"])
        async def brave_image_search(query: str, count: int = 5) -> Any:
            """Return Brave image search results."""
            request = ImagesSearchRequest(q=query, count=count)
            response = await client.images(request)
            return _serialise(response)

        @tool(tags=["search", "videos"])
        async def brave_video_search(query: str, count: int = 5) -> Any:
            """Return Brave video search results."""
            request = VideosSearchRequest(q=query, count=count)
            response = await client.videos(request)
            return _serialise(response)

        @tool(tags=["search", "news"])
        async def brave_news_search(query: str, count: int = 5) -> Any:
            """Return Brave news search results."""
            request = NewsSearchRequest(q=query, count=count)
            response = await client.news(request)
            return _serialise(response)
