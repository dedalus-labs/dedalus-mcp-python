# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import Any

from mcp.server.transport_security import TransportSecuritySettings
import pytest

from dedalus_mcp.server import MCPServer
from dedalus_mcp.server.transports import BaseTransport, StreamableHTTPTransport
from dedalus_mcp.server.transports.asgi import SessionManagerHandler


class DummyTransport(BaseTransport):
    def __init__(self, server: MCPServer, calls: dict[str, object]) -> None:
        super().__init__(server)
        self.calls = calls

    async def run(self, **kwargs: Any) -> None:
        self.calls["called"] = True
        self.calls["kwargs"] = kwargs

    async def stop(self) -> None:
        """Test stub implementation."""


@pytest.mark.anyio
async def test_register_custom_transport_invoked() -> None:
    server = MCPServer("custom-transport")
    calls: dict[str, object] = {}

    server.register_transport("dummy", lambda srv: DummyTransport(srv, calls))

    await server.serve(transport="dummy", foo=42)

    assert calls.get("called") is True
    assert calls.get("kwargs") == {"foo": 42}


def test_default_http_security_settings() -> None:
    server = MCPServer("security-defaults")
    settings = server._http_security_settings  # internal detail, intentional  # noqa: SLF001

    # Defaults are permissive for OSS flexibility
    assert settings.enable_dns_rebinding_protection is False
    assert settings.allowed_hosts == []
    assert settings.allowed_origins == []


def test_http_security_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_DNS_REBINDING_PROTECTION", "true")
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "localhost:*, example.com:443")
    monkeypatch.setenv("MCP_ALLOWED_ORIGINS", "https://example.com, https://other.com")

    server = MCPServer("security-env")
    settings = server._http_security_settings  # noqa: SLF001

    assert settings.enable_dns_rebinding_protection is True
    assert settings.allowed_hosts == ["localhost:*", "example.com:443"]
    assert settings.allowed_origins == ["https://example.com", "https://other.com"]


def test_http_security_params_override_env(monkeypatch: pytest.MonkeyPatch) -> None:
    # Set env vars
    monkeypatch.setenv("MCP_DNS_REBINDING_PROTECTION", "true")
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "env-host:8080")

    # Params should override env
    settings = MCPServer._default_http_security_settings(  # noqa: SLF001
        enable_dns_rebinding_protection=False, allowed_hosts=["param-host:443"]
    )

    assert settings.enable_dns_rebinding_protection is False
    assert settings.allowed_hosts == ["param-host:443"]
    # allowed_origins not passed, should fall back to env (which is empty)
    assert settings.allowed_origins == []


def test_http_security_override() -> None:
    override = TransportSecuritySettings(
        enable_dns_rebinding_protection=True, allowed_hosts=["example.com:443"], allowed_origins=["https://example.com"]
    )

    server = MCPServer("security-override", http_security=override)

    assert server._http_security_settings is override  # noqa: SLF001

    transport = server._transport_for_name("streamable-http")  # noqa: SLF001
    assert isinstance(transport, StreamableHTTPTransport)
    assert transport.security_settings is override

    server.configure_streamable_http_security(None)
    assert server._http_security_settings != override  # noqa: SLF001


@pytest.mark.anyio
async def test_streamable_http_application_rejects_non_http_scope() -> None:
    class DummyManager:
        async def handle_request(self, *_args: object, **_kwargs: object) -> None:
            message = "handle_request should not be invoked for non-http scopes"
            raise AssertionError(message)

    app = SessionManagerHandler(
        session_manager=DummyManager(), transport_label="Streamable HTTP transport", allowed_scopes=("http",)
    )

    async def receive() -> dict[str, object]:
        return {"type": "http.disconnect"}

    async def send(_message: dict[str, object]) -> None:
        message = "send should not be invoked for non-http scopes"
        raise AssertionError(message)

    with pytest.raises(TypeError) as excinfo:
        await app({"type": "lifespan"}, receive, send)

    assert "Streamable HTTP" in str(excinfo.value)
