# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""ServerConfig ergonomics and spec compliance."""

from __future__ import annotations

import pytest

from dedalus_mcp import MCPServer, ServerConfig, SamplingConfig, ElicitationConfig, PingConfig


# --- Defaults ---


def test_completion_limit_default_matches_spec():
    """MCP spec mandates max 100 completions per response."""
    assert ServerConfig().completion_limit == 100


def test_nested_config_defaults():
    cfg = ServerConfig()
    assert cfg.sampling.timeout == 60.0
    assert cfg.sampling.max_concurrent == 4
    assert cfg.elicitation.timeout == 60.0
    assert cfg.ping.phi_threshold == 5.0


# --- Propagation ---


def test_config_flows_to_services():
    config = ServerConfig(
        completion_limit=50,
        sampling=SamplingConfig(timeout=120.0, max_concurrent=8),
        elicitation=ElicitationConfig(timeout=30.0),
        ping=PingConfig(phi_threshold=8.0),
    )
    server = MCPServer("test", config=config)

    assert server.completions._limit == 50
    assert server.sampling._timeout == 120.0
    assert server.sampling._max_concurrent == 8
    assert server.elicitation._timeout == 30.0
    assert server.ping._default_phi == 8.0


def test_zero_config_works():
    server = MCPServer("zero-config")
    assert server.completions._limit == 100
    assert server.sampling._timeout == 60.0


# --- Override semantics ---


def test_explicit_param_overrides_config():
    from dedalus_mcp.types.shared.capabilities import Icon

    config_icon = Icon(src="https://example.com/config.png")
    explicit_icon = Icon(src="https://example.com/explicit.png")

    server = MCPServer("test", config=ServerConfig(icons=[config_icon]), icons=[explicit_icon])
    assert server.icons == [explicit_icon]


def test_none_means_use_config_default():
    from dedalus_mcp.types.shared.capabilities import Icon

    icon = Icon(src="https://example.com/icon.png")
    server = MCPServer("test", config=ServerConfig(icons=[icon]), icons=None)
    assert server.icons == [icon]  # None = "unspecified", falls back to config


def test_empty_list_means_explicitly_none():
    from dedalus_mcp.types.shared.capabilities import Icon

    server = MCPServer("test", config=ServerConfig(icons=[Icon(src="x")]), icons=[])
    assert server.icons == []  # [] = "explicitly no icons"


# --- Completion limit enforcement ---


@pytest.mark.anyio
async def test_completion_truncates_to_limit():
    from dedalus_mcp import completion
    from dedalus_mcp.types.server.completions import CompletionArgument
    from dedalus_mcp.types.server.prompts import PromptReference

    server = MCPServer("test", config=ServerConfig(completion_limit=10))

    with server.binding():

        @completion(prompt="test")
        def many(arg: CompletionArgument, ctx):
            return [f"item-{i}" for i in range(50)]

    result = await server.invoke_completion(
        PromptReference(type="ref/prompt", name="test"), CompletionArgument(name="x", value="")
    )
    assert len(result.values) == 10
    assert result.hasMore is True


@pytest.mark.anyio
async def test_default_enforces_spec_max_100():
    from dedalus_mcp import completion
    from dedalus_mcp.types.server.completions import CompletionArgument
    from dedalus_mcp.types.server.prompts import PromptReference

    server = MCPServer("test")

    with server.binding():

        @completion(prompt="big")
        def overflow(arg: CompletionArgument, ctx):
            return [f"v-{i}" for i in range(200)]

    result = await server.invoke_completion(
        PromptReference(type="ref/prompt", name="big"), CompletionArgument(name="x", value="")
    )
    assert len(result.values) == 100  # spec max
    assert result.hasMore is True


# --- Config immutability ---


def test_nested_configs_are_frozen():
    with pytest.raises(AttributeError):
        SamplingConfig().timeout = 999.0  # type: ignore[misc]


def test_partial_override_preserves_defaults():
    config = ServerConfig(sampling=SamplingConfig(timeout=999.0))
    assert config.elicitation.timeout == 60.0  # untouched
    assert config.sampling.max_concurrent == 4  # other fields preserved
