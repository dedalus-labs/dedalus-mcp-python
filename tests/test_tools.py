from typing import Any

import pytest

from openmcp.server import MCPServer
from openmcp.tool import tool


@pytest.mark.asyncio
async def test_collecting_registers_tools():
    server = MCPServer("demo")

    with server.collecting():
        @tool(description="Adds two numbers")
        def add(a: int, b: int) -> int:
            return a + b

    assert "add" in server.tool_names
    assert server.add(2, 3) == 5  # type: ignore[attr-defined]

    result = await server.invoke_tool("add", a=4, b=7)
    assert not result.isError
    assert result.content
    assert result.content[0].text == "11"


@pytest.mark.asyncio
async def test_allowlist_controls_visibility():
    server = MCPServer("demo")
    server.allow_tools(["slow"])

    with server.collecting():
        @tool()
        def add(a: int, b: int) -> int:
            return a + b

        @tool()
        def slow() -> str:
            return "ok"

    assert "add" not in server.tool_names
    assert "slow" in server.tool_names

    server.allow_tools(["add"])
    server.register_tool(add)  # type: ignore[arg-type]
    assert "add" in server.tool_names
    result = await server.invoke_tool("add", a=1, b=2)
    assert result.content[0].text == "3"


@pytest.mark.asyncio
async def test_registering_outside_collecting():
    server = MCPServer("demo")

    @tool(description="Multiply numbers")
    def multiply(a: int, b: int) -> int:
        return a * b

    assert "multiply" not in server.tool_names

    server.register_tool(multiply)
    assert "multiply" in server.tool_names
    result = await server.invoke_tool("multiply", a=3, b=4)
    assert result.content[0].text == "12"


@pytest.mark.asyncio
async def test_serve_dispatch(monkeypatch):
    http_server = MCPServer("demo-http")
    stdio_server = MCPServer("demo-stdio", transport="stdio")

    called_http: dict[str, Any] = {}
    called_stdio: dict[str, Any] = {}

    async def fake_http(**kwargs: Any):
        called_http["kwargs"] = kwargs

    async def fake_stdio(**kwargs: Any):
        called_stdio["kwargs"] = kwargs

    monkeypatch.setattr(http_server, "serve_streamable_http", fake_http)
    monkeypatch.setattr(stdio_server, "serve_stdio", fake_stdio)

    await http_server.serve(host="0.0.0.0")
    assert called_http == {"kwargs": {"host": "0.0.0.0"}}

    await http_server.serve(transport="streamable-http", port=9999)
    assert called_http == {"kwargs": {"port": 9999}}

    await stdio_server.serve()
    assert called_stdio == {"kwargs": {}}

    await stdio_server.serve(transport="stdio", stateless=True)
    assert called_stdio == {"kwargs": {"stateless": True}}

    with pytest.raises(ValueError):
        await http_server.serve(transport="unknown")


def test_type_adapter_schema():
    server = MCPServer("schema")

    with server.collecting():
        @tool()
        def analytics(a: int, count: int = 1, tags: list[str] | None = None):
            return a

    schema = server._tool_defs["analytics"].inputSchema
    props = schema["properties"]

    assert schema["type"] == "object"
    assert schema["required"] == ["a"]
    assert props["a"]["type"] in {"integer", "number"}
    assert props["count"]["type"] in {"integer", "number"}
    assert props["count"].get("default") == 1
    tags = props["tags"]
    assert any(item.get("type") == "array" for item in tags.get("anyOf", []))
