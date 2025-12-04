# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Test tools capability per MCP 2024-11-05.

Spec: https://modelcontextprotocol.io/specification/2024-11-05/server/tools

Requirements tested:
- Servers that support tools MUST declare the 'tools' capability
- tools/list supports pagination (cursor, nextCursor)
- Tool definition requires name, inputSchema (description optional)
- inputSchema MUST be JSON Schema with type: "object"
- tools/call requires name and arguments
- CallToolResult requires content array
- Tool errors SHOULD use isError flag, not protocol errors (for LLM visibility)
- tools/list_changed notification when listChanged capability is declared
"""

from __future__ import annotations

import pytest

from dedalus_mcp import MCPServer, tool
from dedalus_mcp.types.server.tools import (
    CallToolRequest,
    CallToolRequestParams,
    CallToolResult,
    ListToolsRequest,
    ListToolsResult,
    Tool,
    ToolListChangedNotification,
)
from dedalus_mcp.types.shared.base import PaginatedRequestParams
from dedalus_mcp.types.shared.content import TextContent
from dedalus_mcp.server.core import NotificationFlags


@pytest.mark.anyio
async def test_tool_definition_structure_2024_11_05() -> None:
    """Verify Tool structure matches 2024-11-05 schema requirements."""
    # Per schema: Tool requires name, inputSchema (type: object)
    # description is optional
    tool_def = Tool(
        name="get_weather",
        description="Get current weather information",
        inputSchema={
            "type": "object",
            "properties": {"location": {"type": "string", "description": "City name"}},
            "required": ["location"],
        },
    )

    assert tool_def.name == "get_weather"
    assert tool_def.inputSchema["type"] == "object"
    assert "location" in tool_def.inputSchema["properties"]


@pytest.mark.anyio
async def test_list_tools_request_2024_11_05() -> None:
    """Verify ListToolsRequest structure and pagination support."""
    # Per schema: method = "tools/list", optional cursor in params
    request = ListToolsRequest(params=PaginatedRequestParams(cursor="some-cursor"))

    assert request.method == "tools/list"
    assert request.params.cursor == "some-cursor"


@pytest.mark.anyio
async def test_list_tools_result_2024_11_05() -> None:
    """Verify ListToolsResult structure matches schema."""
    # Per schema: requires tools array, optional nextCursor
    result = ListToolsResult(tools=[Tool(name="test_tool", inputSchema={"type": "object"})], nextCursor="next-page")

    assert len(result.tools) == 1
    assert result.tools[0].name == "test_tool"
    assert result.nextCursor == "next-page"


@pytest.mark.anyio
async def test_call_tool_request_2024_11_05() -> None:
    """Verify CallToolRequest structure matches schema."""
    # Per schema: method = "tools/call", params requires name (arguments optional)
    request = CallToolRequest(params=CallToolRequestParams(name="get_weather", arguments={"location": "New York"}))

    assert request.method == "tools/call"
    assert request.params.name == "get_weather"
    assert request.params.arguments["location"] == "New York"


@pytest.mark.anyio
async def test_call_tool_result_2024_11_05() -> None:
    """Verify CallToolResult structure matches schema."""
    # Per schema: requires content array
    # isError is optional (defaults to false per spec)
    # Content can be TextContent, ImageContent, or EmbeddedResource
    result = CallToolResult(content=[TextContent(type="text", text="Weather data here")], isError=False)

    assert len(result.content) == 1
    assert isinstance(result.content[0], TextContent)
    assert result.content[0].text == "Weather data here"
    assert result.isError is False


@pytest.mark.anyio
async def test_call_tool_error_result_2024_11_05() -> None:
    """Verify tool execution errors use isError flag per spec."""
    # Per spec: "Tool errors SHOULD be reported with isError: true,
    # NOT as protocol-level errors, so the LLM can see them and self-correct"
    result = CallToolResult(
        content=[TextContent(type="text", text="Failed to fetch weather data: API rate limit exceeded")], isError=True
    )

    assert result.isError is True
    assert "rate limit" in result.content[0].text


@pytest.mark.anyio
async def test_tool_list_changed_notification_2024_11_05() -> None:
    """Verify ToolListChangedNotification structure."""
    # Per schema: method = "notifications/tools/list_changed"
    notification = ToolListChangedNotification(params=None)

    assert notification.method == "notifications/tools/list_changed"


@pytest.mark.anyio
async def test_server_declares_tools_capability_2024_11_05() -> None:
    """Verify servers with tools declare the capability (spec requirement)."""
    # Per spec: "Servers that support tools MUST declare the 'tools' capability"
    server = MCPServer(name="test_server", notification_flags=NotificationFlags(tools_changed=True))

    @tool()
    def sample_tool(arg: str) -> str:
        return f"Result: {arg}"

    with server.binding():
        server.register_tool(sample_tool)

    # Verify capability is declared
    from mcp.server.lowlevel.server import NotificationOptions

    caps = server.get_capabilities(
        NotificationOptions(tools_changed=True, prompts_changed=False, resources_changed=False), {}
    )

    assert caps.tools is not None
    assert caps.tools.listChanged is True
