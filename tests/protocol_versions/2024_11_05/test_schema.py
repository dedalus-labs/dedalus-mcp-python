# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Schema compliance tests for MCP 2024-11-05."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

import pytest
from mcp.server.lowlevel.server import NotificationOptions

from dedalus_mcp import MCPServer, prompt, resource, tool, types, versioning
from dedalus_mcp.server import NotificationFlags
from tests.helpers import DummySession, run_with_context

if TYPE_CHECKING:
    pass

VERSION = "2024-11-05"


@pytest.mark.anyio
async def test_initialize_result_matches_schema(assert_schema) -> None:
    server = MCPServer(
        "schema-init",
        notification_flags=NotificationFlags(tools_changed=True, resources_changed=True, prompts_changed=True),
    )

    capabilities = server.get_capabilities(
        NotificationOptions(tools_changed=True, resources_changed=True, prompts_changed=True),
        experimental_capabilities={},
    )

    init = types.InitializeResult(
        protocolVersion=str(versioning.V_2024_11_05),
        capabilities=capabilities,
        serverInfo=types.Implementation(name="SchemaServer", version="1.0.0"),
    )
    payload = init.model_dump(mode="json", by_alias=True, exclude_none=True)

    assert_schema(payload, "#/definitions/InitializeResult", version=VERSION)


@pytest.mark.anyio
async def test_tools_responses_match_schema(assert_schema) -> None:
    server = MCPServer("schema-tools", notification_flags=NotificationFlags(tools_changed=True))

    with server.binding():

        @tool(description="Echo text back to caller")
        def echo(text: str) -> str:
            return text

    session = DummySession("tools")

    # List tools
    list_request = types.ListToolsRequest(params=None)
    list_result = await run_with_context(session, server.tools.list_tools, list_request)
    list_payload = list_result.model_dump(mode="json", by_alias=True, exclude_none=True)
    assert_schema(list_payload, "#/definitions/ListToolsResult", version=VERSION)

    # Call tool
    call_result = await run_with_context(session, server.tools.call_tool, "echo", {"text": "hi"})
    call_payload = call_result.model_dump(mode="json", by_alias=True, exclude_none=True)
    assert_schema(call_payload, "#/definitions/CallToolResult", version=VERSION)


@pytest.mark.anyio
async def test_resources_responses_match_schema(assert_schema) -> None:
    server = MCPServer("schema-resources", notification_flags=NotificationFlags(resources_changed=True))

    with server.binding():

        @resource("file:///schema.txt", name="Schema Notes", mime_type="text/plain")
        def schema_notes() -> str:
            return "dedalus_mcp schema test"

    session = DummySession("resources")

    list_request = types.ListResourcesRequest(params=None)
    list_result = await run_with_context(session, server.resources.list_resources, list_request)
    list_payload = list_result.model_dump(mode="json", by_alias=True, exclude_none=True)
    assert_schema(list_payload, "#/definitions/ListResourcesResult", version=VERSION)

    read_result = await run_with_context(session, server.resources.read, "file:///schema.txt")
    read_payload = read_result.model_dump(mode="json", by_alias=True, exclude_none=True)
    assert_schema(read_payload, "#/definitions/ReadResourceResult", version=VERSION)


@pytest.mark.anyio
async def test_prompts_responses_match_schema(assert_schema) -> None:
    server = MCPServer("schema-prompts", notification_flags=NotificationFlags(prompts_changed=True))

    with server.binding():

        @prompt(
            "greet",
            description="Friendly greeting",
            arguments=[{"name": "name", "description": "Recipient name", "required": True}],
        )
        def greet(arguments: Mapping[str, str] | None):
            name = (arguments or {}).get("name", "friend")
            return types.GetPromptResult(
                description="Friendly greeting",
                messages=[
                    types.PromptMessage(
                        role="assistant", content=types.TextContent(type="text", text=f"Hello, {name}!")
                    )
                ],
            )

    session = DummySession("prompts")

    list_request = types.ListPromptsRequest(params=None)
    list_result = await run_with_context(session, server.prompts.list_prompts, list_request)
    list_payload = list_result.model_dump(mode="json", by_alias=True, exclude_none=True)
    assert_schema(list_payload, "#/definitions/ListPromptsResult", version=VERSION)

    prompt_result = await run_with_context(session, server.prompts.get_prompt, "greet", {"name": "Ada"})
    prompt_payload = prompt_result.model_dump(mode="json", by_alias=True, exclude_none=True)
    assert_schema(prompt_payload, "#/definitions/GetPromptResult", version=VERSION)


@pytest.mark.anyio
async def test_notifications_match_schema(assert_schema) -> None:
    progress_notification = types.ProgressNotification(
        params=types.ProgressNotificationParams(progressToken="token", progress=50, total=100)
    )
    assert_schema(
        progress_notification.model_dump(mode="json", by_alias=True, exclude_none=True),
        "#/definitions/ProgressNotification",
        version=VERSION,
    )

    cancelled_notification = types.CancelledNotification(
        params=types.CancelledNotificationParams(requestId="req-1", reason="user_cancelled")
    )
    assert_schema(
        cancelled_notification.model_dump(mode="json", by_alias=True, exclude_none=True),
        "#/definitions/CancelledNotification",
        version=VERSION,
    )
