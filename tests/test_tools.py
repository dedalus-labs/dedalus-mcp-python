# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from mcp.shared.exceptions import McpError
import pytest

from dedalus_mcp.server import MCPServer, NotificationFlags
from dedalus_mcp.tool import tool
from dedalus_mcp.types.server.tools import ListToolsRequest
from dedalus_mcp.types.shared.base import INVALID_PARAMS, PaginatedRequestParams
from dedalus_mcp.utils.schema import resolve_output_schema
from tests.helpers import DummySession, run_with_context


@pytest.mark.asyncio
async def test_binding_registers_tools():
    """Synchronous tool registration and invocation works correctly."""
    server = MCPServer("demo")

    with server.binding():

        @tool(description="Adds two numbers")
        def add(a: int, b: int) -> int:
            """Synchronous tool function."""
            return a + b

    assert "add" in server.tool_names
    assert server.add(2, 3) == 5  # type: ignore[attr-defined]

    result = await server.invoke_tool("add", a=4, b=7)
    assert not result.isError
    assert result.content
    assert result.content[0].text == "11"
    assert result.structuredContent == {"result": 11}

    # Verify schema is correct for sync tool
    schema = server.tools.definitions["add"].inputSchema
    assert schema["type"] == "object"
    assert "a" in schema["properties"]
    assert "b" in schema["properties"]


@pytest.mark.asyncio
async def test_allowlist_controls_visibility():
    server = MCPServer("demo")
    server.allow_tools(["slow"])

    with server.binding():

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
    assert result.structuredContent == {"result": 3}


@pytest.mark.asyncio
async def test_registering_outside_binding():
    server = MCPServer("demo")

    @tool(description="Multiply numbers")
    def multiply(a: int, b: int) -> int:
        return a * b

    assert "multiply" not in server.tool_names

    server.register_tool(multiply)
    assert "multiply" in server.tool_names
    result = await server.invoke_tool("multiply", a=3, b=4)
    assert result.content[0].text == "12"
    assert result.structuredContent == {"result": 12}


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
    assert called_http == {
        "kwargs": {
            "host": "0.0.0.0",
            "port": 8000,
            "path": "/mcp",
            "log_level": "info",
            "validate": False,
            "announce": True,
        }
    }

    await http_server.serve(transport="streamable-http", port=9999)
    assert called_http == {
        "kwargs": {
            "host": "127.0.0.1",
            "port": 9999,
            "path": "/mcp",
            "log_level": "info",
            "validate": False,
            "announce": True,
        }
    }

    await stdio_server.serve()
    assert called_stdio == {
        "kwargs": {"raise_exceptions": False, "stateless": False, "validate": False, "announce": True}
    }

    await stdio_server.serve(transport="stdio", stateless=True)
    assert called_stdio == {
        "kwargs": {"raise_exceptions": False, "stateless": True, "validate": False, "announce": True}
    }

    with pytest.raises(ValueError):
        await http_server.serve(transport="unknown")


def test_type_adapter_schema():
    server = MCPServer("schema")

    with server.binding():

        @tool()
        def analytics(a: int, count: int = 1, tags: list[str] | None = None):
            return a

    schema = server.tools.definitions["analytics"].inputSchema
    props = schema["properties"]

    assert schema["type"] == "object"
    assert schema["required"] == ["a"]
    assert props["a"]["type"] in {"integer", "number"}
    assert props["count"]["type"] in {"integer", "number"}
    assert props["count"].get("default") == 1
    tags = props["tags"]
    assert any(item.get("type") == "array" for item in tags.get("anyOf", []))


@pytest.mark.anyio
async def test_tools_list_pagination():
    server = MCPServer("tools-pagination")

    for idx in range(120):

        def make_tool(i: int):
            def tool_fn(value: int = 0, _i=i) -> int:
                return _i + value

            tool_fn.__name__ = f"tool_{i:03d}"
            return tool_fn

        server.register_tool(make_tool(idx))

    handler = server.request_handlers[ListToolsRequest]

    first = await run_with_context(DummySession("tools-1"), handler, ListToolsRequest())
    first_result = first.root
    assert len(first_result.tools) == 50
    assert first_result.nextCursor == "50"

    second_request = ListToolsRequest(params=PaginatedRequestParams(cursor="50"))
    second = await run_with_context(DummySession("tools-2"), handler, second_request)
    second_result = second.root
    assert len(second_result.tools) == 50
    assert second_result.nextCursor == "100"

    third_request = ListToolsRequest(params=PaginatedRequestParams(cursor="100"))
    third = await run_with_context(DummySession("tools-3"), handler, third_request)
    third_result = third.root
    assert len(third_result.tools) == 20
    assert third_result.nextCursor is None


@pytest.mark.anyio
async def test_tools_list_invalid_cursor():
    server = MCPServer("tools-invalid-cursor")

    server.register_tool(tool()(lambda: None))
    handler = server.request_handlers[ListToolsRequest]

    request = ListToolsRequest(params=PaginatedRequestParams(cursor="oops"))

    with pytest.raises(McpError) as excinfo:
        await run_with_context(DummySession("tools-invalid"), handler, request)

    assert excinfo.value.error.code == INVALID_PARAMS


@pytest.mark.anyio
async def test_tools_list_cursor_past_end():
    server = MCPServer("tools-past-end")

    for idx in range(3):

        def make_tool(i: int):
            def _fn(_value=i):
                return _value

            _fn.__name__ = f"tiny_{i}"
            return _fn

        server.register_tool(make_tool(idx))

    handler = server.request_handlers[ListToolsRequest]
    request = ListToolsRequest(params=PaginatedRequestParams(cursor="9999"))
    response = await run_with_context(DummySession("tools-past"), handler, request)

    assert response.root.tools == []
    assert response.root.nextCursor is None


@pytest.mark.anyio
async def test_tools_metadata_fields_present():
    server = MCPServer("tools-metadata")

    with server.binding():

        @tool(
            description="Adds two numbers",
            title="Adder",
            output_schema={"type": "object", "properties": {"sum": {"type": "number"}}},
            annotations={"readOnlyHint": True},
            icons=[{"src": "file:///icon.png"}],
        )
        def add(a: int, b: int) -> dict[str, int]:
            return {"sum": a + b}

    handler = server.request_handlers[ListToolsRequest]
    response = await run_with_context(DummySession("tools-metadata"), handler, ListToolsRequest())

    tool_entry = response.root.tools[0]
    assert tool_entry.description == "Adds two numbers"
    assert tool_entry.outputSchema == {"type": "object", "properties": {"sum": {"type": "number"}}}
    assert tool_entry.annotations
    assert tool_entry.annotations.title == "Adder"
    assert tool_entry.annotations.readOnlyHint is True
    assert tool_entry.icons
    assert tool_entry.icons[0].src == "file:///icon.png"


@pytest.mark.anyio
async def test_tools_metadata_with_typed_annotations():
    """Tool decorator accepts ToolAnnotations object instead of dict."""
    from dedalus_mcp.types import ToolAnnotations

    server = MCPServer("tools-typed-annotations")

    with server.binding():

        @tool(
            description="A read-only tool",
            annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False),
        )
        def read_only_op() -> str:
            return "data"

    spec = server.tools._tool_specs["read_only_op"]
    assert isinstance(spec.annotations, ToolAnnotations)
    assert spec.annotations.readOnlyHint is True
    assert spec.annotations.destructiveHint is False


@pytest.mark.anyio
async def test_tools_metadata_with_typed_icons():
    """Tool decorator accepts Icon objects instead of dicts."""
    from dedalus_mcp.types import Icon

    server = MCPServer("tools-typed-icons")

    with server.binding():

        @tool(
            description="Tool with icons",
            icons=[
                Icon(src="file:///primary.png", mimeType="image/png"),
                Icon(src="file:///secondary.svg"),
            ],
        )
        def iconified() -> str:
            return "ok"

    spec = server.tools._tool_specs["iconified"]
    assert spec.icons is not None
    assert len(spec.icons) == 2
    assert all(isinstance(icon, Icon) for icon in spec.icons)
    assert spec.icons[0].src == "file:///primary.png"
    assert spec.icons[0].mimeType == "image/png"
    assert spec.icons[1].src == "file:///secondary.svg"


@pytest.mark.anyio
async def test_tools_metadata_annotations_from_dict():
    """Tool decorator accepts dict and coerces to ToolAnnotations."""
    from dedalus_mcp.types import ToolAnnotations

    server = MCPServer("tools-dict-annotations")

    with server.binding():

        @tool(
            description="Dict-style annotations",
            annotations={"idempotentHint": True},
        )
        def dict_style() -> str:
            return "ok"

    spec = server.tools._tool_specs["dict_style"]
    assert isinstance(spec.annotations, ToolAnnotations)
    assert spec.annotations.idempotentHint is True


@pytest.mark.anyio
async def test_tools_metadata_icons_from_dict():
    """Tool decorator accepts dicts and coerces to Icon objects."""
    from dedalus_mcp.types import Icon

    server = MCPServer("tools-dict-icons")

    with server.binding():

        @tool(
            description="Dict-style icons",
            icons=[{"src": "file:///icon.png", "mimeType": "image/png"}],
        )
        def dict_icons() -> str:
            return "ok"

    spec = server.tools._tool_specs["dict_icons"]
    assert spec.icons is not None
    assert len(spec.icons) == 1
    assert isinstance(spec.icons[0], Icon)
    assert spec.icons[0].src == "file:///icon.png"
    assert spec.icons[0].mimeType == "image/png"


@pytest.mark.anyio
async def test_tools_metadata_typed_objects_in_listing():
    """Typed annotations and icons serialize correctly in tools/list response."""
    from dedalus_mcp.types import Icon, ToolAnnotations

    server = MCPServer("tools-typed-listing")

    with server.binding():

        @tool(
            description="Fully typed",
            annotations=ToolAnnotations(title="Typed Tool", openWorldHint=True),
            icons=[Icon(src="file:///typed.png")],
        )
        def typed_tool() -> str:
            return "ok"

    handler = server.request_handlers[ListToolsRequest]
    response = await run_with_context(DummySession("typed-listing"), handler, ListToolsRequest())

    tool_entry = response.root.tools[0]
    assert tool_entry.annotations is not None
    assert tool_entry.annotations.title == "Typed Tool"
    assert tool_entry.annotations.openWorldHint is True
    assert tool_entry.icons is not None
    assert tool_entry.icons[0].src == "file:///typed.png"


@pytest.mark.anyio
async def test_tool_output_schema_inferred_from_return_type():
    server = MCPServer("tools-output-schema")

    @dataclass
    class Result:
        total: int

    with server.binding():

        @tool()
        async def sum_values(values: list[int]) -> Result:
            return Result(total=sum(values))

    tool_def = server.tools.definitions["sum_values"]
    assert tool_def.outputSchema is not None
    props = tool_def.outputSchema.get("properties")
    assert props and "total" in props

    result = await server.invoke_tool("sum_values", values=[1, 2, 3])
    assert result.structuredContent == {"total": 6}


@pytest.mark.anyio
async def test_tool_output_schema_handles_nested_dataclasses():
    server = MCPServer("tools-output-nested")

    with server.binding():

        @tool()
        async def describe_profile(name: str, street: str | None = None) -> NestedProfile:
            addr = NestedAddress(street=street or "Unknown", postal_code=94107)
            return NestedProfile(name=name, address=addr if street else None, tags=["example"])

    tool_def = server.tools.definitions["describe_profile"]
    schema = tool_def.outputSchema
    assert schema is not None
    expected = resolve_output_schema(NestedProfile).schema
    expected.pop("$defs", None)
    assert schema == expected

    result = await server.tools.call_tool("describe_profile", {"name": "Ada", "street": "Market"})
    assert result.structuredContent == {
        "name": "Ada",
        "address": {"street": "Market", "postal_code": 94107},
        "tags": ["example"],
    }


@pytest.mark.anyio
async def test_tool_output_schema_supports_union_types():
    server = MCPServer("tools-output-union")

    with server.binding():

        @tool()
        async def choose_action(chat: bool) -> UnionAction:
            if chat:
                return UnionAction(kind="chat", payload={"message": "hi"})
            return UnionAction(kind="navigate", payload={"url": "https://example.com"})

    tool_def = server.tools.definitions["choose_action"]
    schema = tool_def.outputSchema
    assert schema is not None
    expected = resolve_output_schema(UnionAction).schema
    expected.pop("$defs", None)
    assert schema == expected

    result = await server.tools.call_tool("choose_action", {"chat": False})
    assert result.structuredContent == {"kind": "navigate", "payload": {"url": "https://example.com"}}


@pytest.mark.anyio
async def test_tool_output_schema_explicit_pass_through():
    server = MCPServer("tools-output-explicit")

    explicit_schema = {
        "type": "object",
        "properties": {"value": {"type": "number"}, "unit": {"type": "string"}},
        "required": ["value", "unit"],
        "additionalProperties": False,
    }

    with server.binding():

        @tool(output_schema=explicit_schema)
        async def measure() -> dict[str, Any]:
            return {"value": 42, "unit": "ms"}

    specification = server.tools.definitions["measure"]
    schema = specification.outputSchema
    assert schema["properties"] == explicit_schema["properties"]
    assert schema["required"] == explicit_schema["required"]

    result = await server.tools.call_tool("measure", {})
    assert result.structuredContent == {"value": 42, "unit": "ms"}


@pytest.mark.anyio
async def test_tool_output_schema_boxes_scalars():
    server = MCPServer("tools-output-scalar")

    with server.binding():

        @tool()
        async def answer() -> int:
            return 7

    schema = server.tools.definitions["answer"].outputSchema
    assert schema is not None
    assert schema["type"] == "object"
    assert schema["properties"] == {"result": {"type": "integer"}}
    assert schema["required"] == ["result"]

    result = await server.tools.call_tool("answer", {})
    assert result.structuredContent == {"result": 7}


@pytest.mark.anyio
async def test_tools_list_changed_notification_enabled():
    server = MCPServer("tools-list-changed", notification_flags=NotificationFlags(tools_changed=True))
    handler = server.request_handlers[ListToolsRequest]
    session = DummySession("tool-observer")

    await run_with_context(session, handler, ListToolsRequest())
    await server.notify_tools_list_changed()

    assert session.notifications
    assert session.notifications[-1].root.method == "notifications/tools/list_changed"


@pytest.mark.anyio
async def test_tools_list_changed_notification_disabled():
    server = MCPServer("tools-list-changed-off")
    handler = server.request_handlers[ListToolsRequest]
    session = DummySession("tool-observer-off")

    await run_with_context(session, handler, ListToolsRequest())
    await server.notify_tools_list_changed()

    assert all(note.root.method != "notifications/tools/list_changed" for note in session.notifications)


@dataclass
class NestedAddress:
    street: str
    postal_code: int


@dataclass
class NestedProfile:
    name: str
    address: NestedAddress | None
    tags: list[str]


@dataclass
class UnionAction:
    kind: Literal["chat", "navigate"]
    payload: dict[str, Any]


# ==============================================================================
# Scope-Gated Tools Tests (OAuth 2.1 Per-Tool Authorization)
# ==============================================================================


@dataclass
class MockAuthContext:
    """Minimal auth context for scope testing."""

    subject: str | None
    scopes: list[str]
    claims: dict[str, Any]


@pytest.mark.anyio
async def test_tool_with_required_scopes_allowed():
    """Tool with required_scopes allows invocation when scopes are granted."""
    server = MCPServer("scope-test")

    with server.binding():

        @tool(required_scopes=["read:data"])
        def read_data() -> str:
            return "secret"

    session = DummySession("scoped")
    auth = MockAuthContext(subject="user", scopes=["read:data", "write:data"], claims={})
    scope = {"dedalus_mcp.auth": auth}

    result = await run_with_context(
        session,
        server.tools.call_tool,
        "read_data",
        {},
        request_scope=scope,
    )

    assert not result.isError
    assert result.content[0].text == "secret"


@pytest.mark.anyio
async def test_tool_with_required_scopes_denied():
    """Tool with required_scopes denies invocation when scopes are missing."""
    server = MCPServer("scope-test-denied")

    with server.binding():

        @tool(required_scopes=["admin:delete"])
        def delete_everything() -> str:
            return "deleted"

    session = DummySession("insufficient")
    auth = MockAuthContext(subject="user", scopes=["read:data"], claims={})
    scope = {"dedalus_mcp.auth": auth}

    result = await run_with_context(
        session,
        server.tools.call_tool,
        "delete_everything",
        {},
        request_scope=scope,
    )

    assert result.isError
    assert "admin:delete" in result.content[0].text
    assert "Missing" in result.content[0].text


@pytest.mark.anyio
async def test_tool_with_multiple_required_scopes():
    """Tool requiring multiple scopes checks all of them."""
    server = MCPServer("multi-scope")

    with server.binding():

        @tool(required_scopes=["scope:a", "scope:b", "scope:c"])
        def multi_scope_tool() -> str:
            return "ok"

    session = DummySession("partial")
    # Only has scope:a and scope:b, missing scope:c
    auth = MockAuthContext(subject="user", scopes=["scope:a", "scope:b"], claims={})
    scope = {"dedalus_mcp.auth": auth}

    result = await run_with_context(
        session,
        server.tools.call_tool,
        "multi_scope_tool",
        {},
        request_scope=scope,
    )

    assert result.isError
    assert "scope:c" in result.content[0].text


@pytest.mark.anyio
async def test_tool_without_required_scopes_ignores_auth():
    """Tool without required_scopes works regardless of auth context."""
    server = MCPServer("no-scope")

    with server.binding():

        @tool()
        def public_tool() -> str:
            return "public"

    session = DummySession("any")
    # Even with no scopes, tool should work
    auth = MockAuthContext(subject="user", scopes=[], claims={})
    scope = {"dedalus_mcp.auth": auth}

    result = await run_with_context(
        session,
        server.tools.call_tool,
        "public_tool",
        {},
        request_scope=scope,
    )

    assert not result.isError
    assert result.content[0].text == "public"


@pytest.mark.anyio
async def test_tool_with_required_scopes_no_auth_context():
    """Tool with required_scopes passes when no auth context (non-OAuth mode)."""
    server = MCPServer("no-auth")

    with server.binding():

        @tool(required_scopes=["admin:delete"])
        def protected_tool() -> str:
            return "allowed in non-oauth mode"

    # No auth context in scope (server not configured for OAuth)
    result = await server.tools.call_tool("protected_tool", {})

    assert not result.isError
    assert result.content[0].text == "allowed in non-oauth mode"


@pytest.mark.asyncio
async def test_tool_spec_stores_required_scopes():
    """ToolSpec stores required_scopes from decorator."""
    server = MCPServer("spec-test")

    with server.binding():

        @tool(required_scopes=["scope:x", "scope:y"])
        def scoped() -> str:
            return "ok"

    spec = server.tools._tool_specs["scoped"]
    assert spec.required_scopes == {"scope:x", "scope:y"}
