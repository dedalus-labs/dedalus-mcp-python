# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Tests for server.collect() and server.collect_from() APIs."""

from __future__ import annotations

from types import ModuleType

import pytest

from dedalus_mcp import MCPServer, ToolSpec, extract_spec, prompt, resource, tool


class TestCollect:
    """Tests for server.collect(*fns)."""

    def test_collect_single_tool(self) -> None:
        @tool(description="Add two numbers")
        def add(a: int, b: int) -> int:
            return a + b

        server = MCPServer("test")
        server.collect(add)

        assert "add" in server.tool_names

    def test_collect_multiple_tools(self) -> None:
        @tool(description="Add")
        def add(a: int, b: int) -> int:
            return a + b

        @tool(description="Multiply")
        def multiply(a: int, b: int) -> int:
            return a * b

        server = MCPServer("test")
        server.collect(add, multiply)

        assert "add" in server.tool_names
        assert "multiply" in server.tool_names

    def test_collect_resource(self) -> None:
        @resource("config://settings")
        def settings() -> str:
            return '{"theme": "dark"}'

        server = MCPServer("test")
        server.collect(settings)

        # Resource should be registered
        assert server.resources is not None

    def test_collect_prompt(self) -> None:
        @prompt("greeting", description="A greeting prompt")
        def greeting(arguments: dict[str, str] | None) -> list[tuple[str, str]]:
            return [("assistant", "Hello!")]

        server = MCPServer("test")
        server.collect(greeting)

        assert "greeting" in server.prompt_names

    def test_collect_mixed_capabilities(self) -> None:
        @tool(description="A tool")
        def my_tool() -> str:
            return "tool"

        @resource("data://test")
        def my_resource() -> str:
            return "resource"

        @prompt("my_prompt")
        def my_prompt(args: dict[str, str] | None) -> list[tuple[str, str]]:
            return [("user", "hello")]

        server = MCPServer("test")
        server.collect(my_tool, my_resource, my_prompt)

        assert "my_tool" in server.tool_names
        assert "my_prompt" in server.prompt_names

    def test_collect_undecorated_function_raises(self) -> None:
        def not_decorated() -> str:
            return "plain function"

        server = MCPServer("test")

        with pytest.raises(ValueError, match="has no Dedalus MCP metadata"):
            server.collect(not_decorated)

    def test_collect_same_function_multiple_servers(self) -> None:
        @tool(description="Shared")
        def shared() -> str:
            return "shared"

        server_a = MCPServer("a")
        server_b = MCPServer("b")

        server_a.collect(shared)
        server_b.collect(shared)

        assert "shared" in server_a.tool_names
        assert "shared" in server_b.tool_names

    def test_collect_with_splat(self) -> None:
        @tool(description="One")
        def one() -> int:
            return 1

        @tool(description="Two")
        def two() -> int:
            return 2

        tools = [one, two]
        server = MCPServer("test")
        server.collect(*tools)

        assert "one" in server.tool_names
        assert "two" in server.tool_names


class TestCollectFrom:
    """Tests for server.collect_from(*modules)."""

    def test_collect_from_module(self) -> None:
        # Create a mock module with decorated functions
        mock_module = ModuleType("mock_tools")

        @tool(description="Module tool")
        def module_tool() -> str:
            return "from module"

        mock_module.module_tool = module_tool  # type: ignore[attr-defined]

        server = MCPServer("test")
        server.collect_from(mock_module)

        assert "module_tool" in server.tool_names

    def test_collect_from_skips_private(self) -> None:
        mock_module = ModuleType("mock_private")

        @tool(description="Private tool")
        def _private_tool() -> str:
            return "private"

        mock_module._private_tool = _private_tool  # type: ignore[attr-defined]

        server = MCPServer("test")
        server.collect_from(mock_module)

        # Private functions should be skipped
        assert "_private_tool" not in server.tool_names

    def test_collect_from_skips_undecorated(self) -> None:
        mock_module = ModuleType("mock_mixed")

        @tool(description="Decorated")
        def decorated() -> str:
            return "decorated"

        def not_decorated() -> str:
            return "not decorated"

        mock_module.decorated = decorated  # type: ignore[attr-defined]
        mock_module.not_decorated = not_decorated  # type: ignore[attr-defined]

        server = MCPServer("test")
        # Should not raise, just skip undecorated
        server.collect_from(mock_module)

        assert "decorated" in server.tool_names

    def test_collect_from_multiple_modules(self) -> None:
        module_a = ModuleType("module_a")
        module_b = ModuleType("module_b")

        @tool(description="From A")
        def tool_a() -> str:
            return "a"

        @tool(description="From B")
        def tool_b() -> str:
            return "b"

        module_a.tool_a = tool_a  # type: ignore[attr-defined]
        module_b.tool_b = tool_b  # type: ignore[attr-defined]

        server = MCPServer("test")
        server.collect_from(module_a, module_b)

        assert "tool_a" in server.tool_names
        assert "tool_b" in server.tool_names


class TestExtractSpec:
    """Tests for extract_spec()."""

    def test_extract_tool_spec(self) -> None:
        @tool(description="Test tool")
        def my_tool() -> str:
            return "test"

        spec = extract_spec(my_tool)
        assert spec is not None
        assert isinstance(spec, ToolSpec)
        assert spec.name == "my_tool"

    def test_extract_returns_none_for_undecorated(self) -> None:
        def plain() -> str:
            return "plain"

        spec = extract_spec(plain)
        assert spec is None

    def test_extract_from_resource(self) -> None:
        @resource("test://uri")
        def my_resource() -> str:
            return "data"

        spec = extract_spec(my_resource)
        assert spec is not None

    def test_extract_from_prompt(self) -> None:
        @prompt("test_prompt")
        def my_prompt(args: dict[str, str] | None) -> list[tuple[str, str]]:
            return []

        spec = extract_spec(my_prompt)
        assert spec is not None


class TestIntegration:
    """Integration tests for collect() workflow."""

    @pytest.mark.asyncio
    async def test_collect_then_invoke(self) -> None:
        @tool(description="Add numbers")
        def add(a: int, b: int) -> int:
            return a + b

        server = MCPServer("test")
        server.collect(add)

        result = await server.invoke_tool("add", a=2, b=3)
        assert result.content[0].text == "5"

    def test_collect_idempotent(self) -> None:
        @tool(description="Test")
        def test_fn() -> str:
            return "test"

        server = MCPServer("test")
        server.collect(test_fn)
        server.collect(test_fn)  # Should not raise

        # Tool should still be registered
        assert "test_fn" in server.tool_names
