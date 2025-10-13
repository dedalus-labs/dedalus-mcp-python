"""Prompt capability tests.

Exercises the prompt lifecycle defined in
``docs/mcp/spec/schema-reference/prompts-list.md`` and
``docs/mcp/spec/schema-reference/prompts-get.md``.
"""

from __future__ import annotations

import pytest

from mcp.shared.exceptions import McpError

from openmcp import MCPServer, prompt, types


@pytest.mark.anyio
async def test_prompt_registration_and_rendering() -> None:
    server = MCPServer("prompts")

    with server.collecting():

        @prompt(
            "greet",
            description="Generate a greeting",
            arguments=[{"name": "name", "description": "Person to greet", "required": True}],
        )
        def greet(arguments: dict[str, str]):
            name = arguments["name"]
            return [
                ("assistant", "You are a helpful assistant."),
                ("user", f"Say hello to {name}"),
            ]

    assert server.prompt_names == ["greet"]

    result = await server.invoke_prompt("greet", arguments={"name": "Ada"})
    assert result.description == "Generate a greeting"
    assert len(result.messages) == 2
    assert result.messages[1].content.type == "text"
    assert "Ada" in result.messages[1].content.text


@pytest.mark.anyio
async def test_prompt_missing_argument_raises_mcp_error() -> None:
    server = MCPServer("prompts-missing")

    with server.collecting():

        @prompt(
            "needs-arg",
            arguments=[{"name": "topic", "required": True}],
        )
        def _needs_arg(arguments: dict[str, str]):  # pragma: no cover - exercised via invocation
            return [("assistant", f"Topic is {arguments['topic']}")]

    with pytest.raises(McpError) as excinfo:
        await server.invoke_prompt("needs-arg")

    assert excinfo.value.error.code == types.INVALID_PARAMS


@pytest.mark.anyio
async def test_prompt_custom_mapping_result() -> None:
    server = MCPServer("prompts-mapping")

    with server.collecting():

        @prompt("status")
        async def status_prompt(_: dict[str, str]):
            return {
                "description": "Status template",
                "messages": [
                    ("assistant", "You summarize status reports."),
                ],
            }

    result = await server.invoke_prompt("status")
    assert result.description == "Status template"
    assert result.messages[0].role == "assistant"
