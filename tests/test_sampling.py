# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

from __future__ import annotations

import asyncio
from typing import Any

from mcp.shared.exceptions import McpError
import pytest

from dedalus_mcp import MCPServer
from dedalus_mcp.types.client.sampling import (
    CreateMessageRequest,
    CreateMessageRequestParams,
    CreateMessageResult,
    SamplingMessage,
)
from dedalus_mcp.types.messages import ServerRequest
from dedalus_mcp.types.shared.base import ErrorData, INTERNAL_ERROR, METHOD_NOT_FOUND
from dedalus_mcp.types.shared.capabilities import ClientCapabilities
from dedalus_mcp.types.shared.content import TextContent
from tests.helpers import DummySession, run_with_context


class FakeSession(DummySession):
    def __init__(self) -> None:
        super().__init__("sampling")
        self.capable = True
        self.requests: list[ServerRequest] = []
        self.result = CreateMessageResult(
            role="assistant", content=TextContent(type="text", text="ok"), model="demo", stopReason="endTurn"
        )

    def check_client_capability(self, capability: ClientCapabilities) -> bool:  # type: ignore[override]
        return self.capable

    async def send_request(self, request: ServerRequest, result_type: type[Any], *, progress_callback=None) -> Any:
        self.requests.append(request)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@pytest.mark.anyio
async def test_sampling_missing_capability_raises_method_not_found() -> None:
    server = MCPServer("sampling")
    session = FakeSession()
    session.capable = False

    params = CreateMessageRequestParams(
        messages=[SamplingMessage(role="user", content=TextContent(type="text", text="hi"))], maxTokens=10
    )

    with pytest.raises(McpError) as exc:
        await run_with_context(session, server.request_sampling, params)
    assert exc.value.error.code == METHOD_NOT_FOUND


@pytest.mark.anyio
async def test_sampling_successful_roundtrip_records_request() -> None:
    server = MCPServer("sampling")
    session = FakeSession()

    params = CreateMessageRequestParams(
        messages=[SamplingMessage(role="user", content=TextContent(type="text", text="hello"))], maxTokens=32
    )

    result = await run_with_context(session, server.request_sampling, params)
    assert isinstance(result, CreateMessageResult)
    assert session.requests
    sent = session.requests[0].root
    assert isinstance(sent, CreateMessageRequest)
    assert sent.params.maxTokens == 32


@pytest.mark.anyio
async def test_sampling_propagates_client_error() -> None:
    server = MCPServer("sampling")
    session = FakeSession()
    session.result = McpError(ErrorData(code=-1, message="User rejected sampling request"))

    params = CreateMessageRequestParams(
        messages=[SamplingMessage(role="user", content=TextContent(type="text", text="hello"))], maxTokens=32
    )

    with pytest.raises(McpError) as exc:
        await run_with_context(session, server.request_sampling, params)
    assert exc.value.error.message == "User rejected sampling request"


@pytest.mark.anyio
async def test_sampling_timeout_triggers_circuit_breaker() -> None:
    server = MCPServer("sampling")

    session = FakeSession()

    async def slow_send(request, result_type, progress_callback=None):
        await asyncio.sleep(1.0)
        return session.result

    session.send_request = slow_send  # type: ignore[assignment]

    params = CreateMessageRequestParams(
        messages=[SamplingMessage(role="user", content=TextContent(type="text", text="slow"))], maxTokens=4
    )

    server.sampling._timeout = 0.01  # type: ignore[attr-defined]

    with pytest.raises(McpError) as exc:
        await run_with_context(session, server.request_sampling, params)
    assert exc.value.error.code == INTERNAL_ERROR
