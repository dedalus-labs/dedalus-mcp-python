# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Test sampling capability, per MCP 2024-11-05.

Spec: https://modelcontextprotocol.io/specification/2024-11-05/client/sampling

Requirements tested:
- sampling/createMessage request structure
- CreateMessageRequest requires maxTokens, messages
- CreateMessageResult requires role, content, model
- ModelPreferences optional hints for model selection
- includeContext enum values
"""

from __future__ import annotations

import pytest

from openmcp.types.client.sampling import (
    CreateMessageRequest,
    CreateMessageRequestParams,
    CreateMessageResult,
    ModelHint,
    ModelPreferences,
    SamplingMessage,
)
from openmcp.types.shared.content import TextContent


@pytest.mark.anyio
async def test_create_message_request_2024_11_05() -> None:
    """Verify CreateMessageRequest structure."""
    # Per schema: method = "sampling/createMessage"
    # params requires maxTokens, messages
    # optional: modelPreferences, systemPrompt, includeContext, temperature, stopSequences, metadata
    request = CreateMessageRequest(
        params=CreateMessageRequestParams(
            messages=[SamplingMessage(role="user", content=TextContent(type="text", text="Hello"))],
            maxTokens=100,
            systemPrompt="You are a helpful assistant",
            temperature=0.7,
        )
    )

    assert request.method == "sampling/createMessage"
    assert request.params.maxTokens == 100
    assert len(request.params.messages) == 1
    assert request.params.systemPrompt == "You are a helpful assistant"


@pytest.mark.anyio
async def test_sampling_message_2024_11_05() -> None:
    """Verify SamplingMessage structure."""
    # Per schema: requires role, content
    # content can be TextContent or ImageContent
    message = SamplingMessage(role="assistant", content=TextContent(type="text", text="Response here"))

    assert message.role == "assistant"
    assert isinstance(message.content, TextContent)


@pytest.mark.anyio
async def test_create_message_result_2024_11_05() -> None:
    """Verify CreateMessageResult structure."""
    # Per schema: requires role, content, model
    # optional: stopReason
    result = CreateMessageResult(
        role="assistant",
        content=TextContent(type="text", text="Generated response"),
        model="claude-3-opus",
        stopReason="end_turn",
    )

    assert result.role == "assistant"
    assert result.model == "claude-3-opus"
    assert result.stopReason == "end_turn"


@pytest.mark.anyio
async def test_model_preferences_2024_11_05() -> None:
    """Verify ModelPreferences structure."""
    # Per schema: optional hints, costPriority, speedPriority, intelligencePriority
    prefs = ModelPreferences(
        hints=[ModelHint(name="claude-3-sonnet")], costPriority=0.3, speedPriority=0.5, intelligencePriority=0.9
    )

    assert len(prefs.hints) == 1
    assert prefs.hints[0].name == "claude-3-sonnet"
    assert prefs.costPriority == 0.3


@pytest.mark.anyio
async def test_include_context_enum_2024_11_05() -> None:
    """Verify includeContext enum values."""
    # Per schema: enum values are "none", "thisServer", "allServers"
    for value in ["none", "thisServer", "allServers"]:
        request = CreateMessageRequest(
            params=CreateMessageRequestParams(
                messages=[SamplingMessage(role="user", content=TextContent(type="text", text="Test"))],
                maxTokens=50,
                includeContext=value,
            )
        )
        assert request.params.includeContext == value
