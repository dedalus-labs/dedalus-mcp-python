# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import Any

from mcp.shared.exceptions import McpError
import pytest

from dedalus_mcp import MCPServer
from dedalus_mcp.types.client.elicitation import ElicitRequest, ElicitRequestParams, ElicitResult
from dedalus_mcp.types.messages import ServerRequest
from dedalus_mcp.types.shared.base import ErrorData, METHOD_NOT_FOUND
from dedalus_mcp.types.shared.capabilities import ClientCapabilities
from tests.helpers import run_with_context


class FakeSession:
    def __init__(self, result: Any) -> None:
        self.result = result
        self.capable = True
        self.calls: list[ServerRequest] = []

    def check_client_capability(self, capability: ClientCapabilities) -> bool:  # type: ignore[override]
        return self.capable

    async def send_request(self, request, result_type):
        self.calls.append(request)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@pytest.mark.anyio
async def test_elicitation_requires_capability() -> None:
    server = MCPServer("elicitation")
    session = FakeSession(ElicitResult(action="accept", content={}))
    session.capable = False

    params = ElicitRequestParams(
        message="Provide a value",
        requestedSchema={"type": "object", "properties": {"value": {"type": "string"}}, "required": ["value"]},
    )

    with pytest.raises(McpError) as exc:
        await run_with_context(session, server.request_elicitation, params)
    assert exc.value.error.code == METHOD_NOT_FOUND


@pytest.mark.anyio
async def test_elicitation_happy_path_records_call() -> None:
    result = ElicitResult(action="accept", content={"value": "yes"})
    server = MCPServer("elicitation")
    session = FakeSession(result)

    params = ElicitRequestParams(
        message="Provide a value", requestedSchema={"type": "object", "properties": {"value": {"type": "string"}}}
    )

    response = await run_with_context(session, server.request_elicitation, params)
    assert response.action == "accept"
    assert session.calls
    assert isinstance(session.calls[0].root, ElicitRequest)


@pytest.mark.anyio
async def test_elicitation_propagates_client_error() -> None:
    error = McpError(ErrorData(code=-1, message="User declined"))
    server = MCPServer("elicitation")
    session = FakeSession(error)

    params = ElicitRequestParams(
        message="Provide a value", requestedSchema={"type": "object", "properties": {"value": {"type": "string"}}}
    )

    with pytest.raises(McpError) as exc:
        await run_with_context(session, server.request_elicitation, params)
    assert exc.value.error.message == "User declined"


@pytest.mark.anyio
async def test_elicitation_schema_validation() -> None:
    server = MCPServer("elicitation")
    session = FakeSession(ElicitResult(action="accept", content={}))

    bad_params = ElicitRequestParams(message="Provide", requestedSchema={"type": "object", "properties": {}})

    with pytest.raises(McpError):
        await run_with_context(session, server.request_elicitation, bad_params)
