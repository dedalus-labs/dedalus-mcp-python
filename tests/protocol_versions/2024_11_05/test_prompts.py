# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Test prompts capability per MCP 2024-11-05.

Spec: https://modelcontextprotocol.io/specification/2024-11-05/server/prompts

Requirements tested:
- Prompt definition requires name (description, arguments optional)
- prompts/list supports pagination
- prompts/get requires name, optional arguments (for templating)
- GetPromptResult requires messages array
- PromptMessage requires role and content
- prompts/list_changed notification when capability declared
"""

from __future__ import annotations

import pytest

from dedalus_mcp.types.server.prompts import (
    GetPromptRequest,
    GetPromptRequestParams,
    GetPromptResult,
    ListPromptsRequest,
    ListPromptsResult,
    Prompt,
    PromptArgument,
    PromptListChangedNotification,
    PromptMessage,
)
from dedalus_mcp.types.shared.base import PaginatedRequestParams
from dedalus_mcp.types.shared.content import TextContent


@pytest.mark.anyio
async def test_prompt_definition_2024_11_05() -> None:
    """Verify Prompt structure matches 2024-11-05 schema."""
    # Per schema: requires name. Optional: description, arguments
    prompt = Prompt(
        name="code_review",
        description="Review code for issues",
        arguments=[PromptArgument(name="code", description="The code to review", required=True)],
    )

    assert prompt.name == "code_review"
    assert len(prompt.arguments) == 1
    assert prompt.arguments[0].name == "code"
    assert prompt.arguments[0].required is True


@pytest.mark.anyio
async def test_list_prompts_request_2024_11_05() -> None:
    """Verify ListPromptsRequest supports pagination."""
    # Per schema: method = "prompts/list", optional cursor
    request = ListPromptsRequest(params=PaginatedRequestParams(cursor="page-cursor"))

    assert request.method == "prompts/list"
    assert request.params.cursor == "page-cursor"


@pytest.mark.anyio
async def test_list_prompts_result_2024_11_05() -> None:
    """Verify ListPromptsResult structure."""
    # Per schema: requires prompts array, optional nextCursor
    result = ListPromptsResult(prompts=[Prompt(name="test_prompt")], nextCursor="next-page")

    assert len(result.prompts) == 1
    assert result.nextCursor == "next-page"


@pytest.mark.anyio
async def test_get_prompt_request_2024_11_05() -> None:
    """Verify GetPromptRequest structure."""
    # Per schema: method = "prompts/get", params requires name, optional arguments
    request = GetPromptRequest(params=GetPromptRequestParams(name="code_review", arguments={"code": "def foo(): pass"}))

    assert request.method == "prompts/get"
    assert request.params.name == "code_review"
    assert request.params.arguments["code"] == "def foo(): pass"


@pytest.mark.anyio
async def test_get_prompt_result_2024_11_05() -> None:
    """Verify GetPromptResult structure."""
    # Per schema: requires messages array, optional description
    result = GetPromptResult(
        description="Code review prompt",
        messages=[PromptMessage(role="user", content=TextContent(type="text", text="Review this code"))],
    )

    assert result.description == "Code review prompt"
    assert len(result.messages) == 1
    assert result.messages[0].role == "user"


@pytest.mark.anyio
async def test_prompt_message_2024_11_05() -> None:
    """Verify PromptMessage structure."""
    # Per schema: requires role and content
    # content can be TextContent, ImageContent, or EmbeddedResource
    message = PromptMessage(role="assistant", content=TextContent(type="text", text="Here's my review"))

    assert message.role == "assistant"
    assert isinstance(message.content, TextContent)


@pytest.mark.anyio
async def test_prompt_list_changed_notification_2024_11_05() -> None:
    """Verify PromptListChangedNotification structure."""
    # Per schema: method = "notifications/prompts/list_changed"
    notification = PromptListChangedNotification(params=None)

    assert notification.method == "notifications/prompts/list_changed"
