# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Testing patterns for Dedalus MCP servers.

Dedalus MCP's decoupled registration model makes testing straightforward.
No global state, no mocking decorators, no teardown headaches.

This file shows pytest patterns that work.

Usage:
    uv run pytest examples/patterns/testing.py -v
"""

import pytest
from dedalus_mcp import MCPServer, tool, resource, prompt


# ============================================================================
# Your tools (in a separate module in real code)
# ============================================================================


@tool(description="Add two numbers")
def add(a: int, b: int) -> int:
    return a + b


@tool(description="Multiply two numbers")
def multiply(a: int, b: int) -> int:
    return a * b


@tool(description="Divide two numbers")
def divide(a: int, b: int) -> float:
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b


@resource(uri="config://version", name="Version")
def version() -> str:
    return "1.0.0"


@prompt(name="greeting", description="A greeting prompt")
def greeting_prompt(args: dict) -> list[dict]:
    name = args.get("name", "World")
    return [{"role": "assistant", "content": f"Hello, {name}!"}]


# ============================================================================
# Test fixtures
# ============================================================================


@pytest.fixture
def server() -> MCPServer:
    """Fresh server for each test. No global state."""
    srv = MCPServer("test-server")
    srv.collect(add, multiply, divide, version, greeting_prompt)
    return srv


@pytest.fixture
def math_only_server() -> MCPServer:
    """Server with only math tools."""
    srv = MCPServer("math-server")
    srv.collect(add, multiply)
    return srv


# ============================================================================
# Unit tests for tools
# ============================================================================


class TestToolRegistration:
    """Test that tools register correctly."""

    def test_tools_registered(self, server: MCPServer) -> None:
        """All collected tools should be listed."""
        names = server.tools.tool_names
        assert "add" in names
        assert "multiply" in names
        assert "divide" in names

    def test_selective_registration(self, math_only_server: MCPServer) -> None:
        """Only collected tools should be registered."""
        names = math_only_server.tools.tool_names
        assert "add" in names
        assert "multiply" in names
        assert "divide" not in names  # Not collected

    def test_same_tool_different_servers(self) -> None:
        """Same decorated function can register to multiple servers."""
        server_a = MCPServer("a")
        server_b = MCPServer("b")

        server_a.collect(add)
        server_b.collect(add, multiply)

        assert server_a.tools.tool_names == ["add"]
        assert set(server_b.tools.tool_names) == {"add", "multiply"}


class TestToolExecution:
    """Test tool behavior directly (no MCP protocol)."""

    def test_add(self) -> None:
        """Test add directly."""
        assert add(2, 3) == 5
        assert add(-1, 1) == 0

    def test_multiply(self) -> None:
        """Test multiply directly."""
        assert multiply(3, 4) == 12
        assert multiply(0, 100) == 0

    def test_divide(self) -> None:
        """Test divide with normal and error cases."""
        assert divide(10, 2) == 5.0
        assert divide(7, 2) == 3.5

    def test_divide_by_zero(self) -> None:
        """Division by zero should raise."""
        with pytest.raises(ValueError, match="Cannot divide by zero"):
            divide(10, 0)


class TestAllowList:
    """Test tool filtering via allow-lists."""

    def test_allow_list_filters_tools(self, server: MCPServer) -> None:
        """Allow-list should hide tools."""
        # Initially all tools visible
        assert len(server.tools.tool_names) == 3

        # Filter to add only
        server.tools.allow_tools(["add"])
        assert server.tools.tool_names == ["add"]

        # Reset
        server.tools.allow_tools(None)
        assert len(server.tools.tool_names) == 3


# ============================================================================
# Integration test patterns (with real MCP client)
# ============================================================================


@pytest.fixture
async def running_server(server: MCPServer):
    """Start server in background for integration tests."""
    import asyncio
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def serve_background():
        task = asyncio.create_task(server.serve(port=18765))
        await asyncio.sleep(0.5)  # Wait for startup
        try:
            yield server
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async with serve_background() as srv:
        yield srv


@pytest.mark.asyncio
async def test_client_integration(running_server: MCPServer) -> None:
    """Full integration test with real client."""
    from dedalus_mcp.client import MCPClient

    client = await MCPClient.connect("http://127.0.0.1:18765/mcp")
    try:
        # List tools
        tools = await client.list_tools()
        tool_names = [t.name for t in tools.tools]
        assert "add" in tool_names

        # Call tool
        result = await client.call_tool("add", {"a": 10, "b": 20})
        assert "30" in result.content[0].text
    finally:
        await client.close()


# ============================================================================
# Running this file directly
# ============================================================================

if __name__ == "__main__":
    print("Run with: uv run pytest examples/patterns/testing.py -v")
    print("\nThis demonstrates testing patterns for Dedalus MCP.")
    print("\nKey patterns:")
    print("  1. Fresh server per test (no global state)")
    print("  2. Selective tool collection per fixture")
    print("  3. Direct function testing (no MCP overhead)")
    print("  4. Allow-list testing")
    print("  5. Integration tests with real client")
