# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Tests for completion capability.

These cases track the behavior defined in
https://modelcontextprotocol.io/specification/2024-11-05/server/utilities/completion
"""

from __future__ import annotations

import pytest

from dedalus_mcp import MCPServer, completion
from dedalus_mcp.completion import CompletionResult
from dedalus_mcp.types.server.completions import CompletionArgument, CompletionContext, ResourceTemplateReference
from dedalus_mcp.types.server.prompts import PromptReference


@pytest.mark.anyio
async def test_prompt_completion_registration() -> None:
    """Prompt completions should respond with registered values (spec receipts)."""
    server = MCPServer("comp")

    with server.binding():

        @completion(prompt="code_review")
        def language(argument: CompletionArgument, context: CompletionContext | None):
            assert argument.name == "language"
            assert argument.value.startswith("py")
            return ["python", "pytorch", "pyside"]

    ref = PromptReference(type="ref/prompt", name="code_review")
    argument = CompletionArgument(name="language", value="py")
    result = await server.invoke_completion(ref, argument)
    assert result is not None
    assert result.values == ["python", "pytorch", "pyside"]
    assert result.hasMore is None


@pytest.mark.anyio
async def test_resource_completion_limit_enforced() -> None:
    """Servers must not return more than 100 values (completion spec)."""
    server = MCPServer("comp-limit")

    long_list = [f"item-{i}" for i in range(150)]

    with server.binding():

        @completion(resource="file:///{path}")
        def path_completion(argument: CompletionArgument, context: CompletionContext | None):
            assert argument.name == "path"
            return long_list

    ref = ResourceTemplateReference(type="ref/resource", uri="file:///{path}")
    argument = CompletionArgument(name="path", value="")
    result = await server.invoke_completion(ref, argument)
    assert result is not None
    assert len(result.values) == 100
    assert result.values[0] == "item-0"
    assert result.values[-1] == "item-99"
    assert result.hasMore is True


@pytest.mark.anyio
async def test_missing_completion_returns_empty() -> None:
    """Unknown completions resolve to empty arrays as per spec tolerance."""
    server = MCPServer("comp-missing")
    ref = PromptReference(type="ref/prompt", name="unknown")
    argument = CompletionArgument(name="language", value="py")
    result = await server.invoke_completion(ref, argument)
    assert result is not None
    assert result.values == []
    assert result.total is None


@pytest.mark.anyio
async def test_completion_result_dataclass() -> None:
    server = MCPServer("comp-result")

    with server.binding():

        @completion(prompt="scenario")
        def scenario(argument: CompletionArgument, context: CompletionContext | None):
            return CompletionResult(values=["alpha", "beta"], total=2, has_more=False)

    ref = PromptReference(type="ref/prompt", name="scenario")
    argument = CompletionArgument(name="label", value="a")
    result = await server.invoke_completion(ref, argument)
    assert result is not None
    assert result.values == ["alpha", "beta"]
    assert result.total == 2
    assert result.hasMore is False


@pytest.mark.anyio
async def test_completion_mapping_with_has_more() -> None:
    server = MCPServer("comp-mapping")

    with server.binding():

        @completion(resource="file:///{path}")
        def mapping_completion(argument: CompletionArgument, context: CompletionContext | None):
            return {"values": ["x", "y"], "hasMore": True}

    ref = ResourceTemplateReference(type="ref/resource", uri="file:///{path}")
    argument = CompletionArgument(name="path", value="")
    result = await server.invoke_completion(ref, argument)
    assert result is not None
    assert result.values == ["x", "y"]
    assert result.hasMore is True


@pytest.mark.anyio
async def test_completion_receives_context() -> None:
    server = MCPServer("comp-context")

    with server.binding():

        @completion(prompt="contextual")
        def contextual(argument: CompletionArgument, context: CompletionContext | None):
            assert context is not None
            assert context.root == "root-id"
            return [argument.value.upper()]

    ref = PromptReference(type="ref/prompt", name="contextual")
    argument = CompletionArgument(name="word", value="mix")
    ctx = CompletionContext(root="root-id", path=["word"])
    result = await server.invoke_completion(ref, argument, context=ctx)
    assert result is not None
    assert result.values == ["MIX"]
