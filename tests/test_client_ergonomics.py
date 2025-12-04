# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Tests for the ergonomic MCPClient API.

These tests validate the script-friendly client interface without mandatory
context managers. The design follows Stainless SDK ergonomics with Speakeasy's
correctness guarantees (weakref.finalize for cleanup).
"""

from __future__ import annotations

import warnings
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import anyio
import pytest

from dedalus_mcp.types.lifecycle import InitializeResult
from dedalus_mcp.types.shared.capabilities import Implementation, ServerCapabilities
from dedalus_mcp.types.shared.primitives import LATEST_PROTOCOL_VERSION


# ---------------------------------------------------------------------
# Fake session for unit tests
# ---------------------------------------------------------------------


class FakeClientSession:
    """Minimal fake for mcp.client.session.ClientSession."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.closed = False

    async def __aenter__(self) -> "FakeClientSession":
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.closed = True

    async def initialize(self) -> InitializeResult:
        return InitializeResult(
            protocolVersion=LATEST_PROTOCOL_VERSION,
            capabilities=ServerCapabilities(),
            serverInfo=Implementation(name="fake", version="0.0.0"),
        )


# ---------------------------------------------------------------------
# Phase 1: Core Lifecycle
# ---------------------------------------------------------------------


@pytest.mark.anyio
async def test_connect_returns_initialized_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """connect() should return a client that's already initialized and ready to use."""
    from dedalus_mcp.client import MCPClient

    # We'll mock the transport layer to avoid network
    fake_session = FakeClientSession()

    async def fake_transport(*args: Any, **kwargs: Any):
        """Fake async context manager that yields streams."""
        read_stream, _ = anyio.create_memory_object_stream(0)
        _, write_stream = anyio.create_memory_object_stream(0)

        class FakeTransportCtx:
            async def __aenter__(self):
                return (read_stream, write_stream, lambda: None)

            async def __aexit__(self, *args):
                pass

        return FakeTransportCtx()

    monkeypatch.setattr("dedalus_mcp.client.core.ClientSession", lambda *a, **kw: fake_session)

    # Use the new connect() API
    client = await MCPClient.connect(
        "http://localhost:8000/mcp",
        _transport_override=fake_session,  # Skip actual transport
    )

    try:
        assert client.initialize_result is not None
        assert client.initialize_result.serverInfo.name == "fake"
    finally:
        await client.close()


@pytest.mark.anyio
async def test_close_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Calling close() multiple times should be safe (no-op on second call)."""
    from dedalus_mcp.client import MCPClient

    fake_session = FakeClientSession()
    monkeypatch.setattr("dedalus_mcp.client.core.ClientSession", lambda *a, **kw: fake_session)

    client = await MCPClient.connect("http://localhost:8000/mcp", _transport_override=fake_session)

    await client.close()
    # Second close should not raise
    await client.close()

    assert client._closed is True


@pytest.mark.anyio
async def test_session_after_close_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Accessing session after close() should raise RuntimeError."""
    from dedalus_mcp.client import MCPClient

    fake_session = FakeClientSession()
    monkeypatch.setattr("dedalus_mcp.client.core.ClientSession", lambda *a, **kw: fake_session)

    client = await MCPClient.connect("http://localhost:8000/mcp", _transport_override=fake_session)

    await client.close()

    with pytest.raises(RuntimeError, match="closed|not connected"):
        _ = client.session


@pytest.mark.anyio
async def test_finalizer_warns_on_unclosed(monkeypatch: pytest.MonkeyPatch) -> None:
    """If close() wasn't called, the finalizer should log a warning."""
    from dedalus_mcp.client import MCPClient

    fake_session = FakeClientSession()
    monkeypatch.setattr("dedalus_mcp.client.core.ClientSession", lambda *a, **kw: fake_session)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")

        client = await MCPClient.connect("http://localhost:8000/mcp", _transport_override=fake_session)

        # Don't call close(), just delete the reference
        client_id = id(client)
        del client

        # Force garbage collection to trigger finalizer
        import gc

        gc.collect()

        # Check that a warning was issued
        resource_warnings = [w for w in caught if "MCPClient" in str(w.message) or "close" in str(w.message).lower()]
        assert len(resource_warnings) >= 1, f"Expected ResourceWarning, got: {[str(w.message) for w in caught]}"


# ---------------------------------------------------------------------
# Phase 2: Context Manager Support
# ---------------------------------------------------------------------


@pytest.mark.anyio
async def test_context_manager_closes_on_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    """async with MCPClient.connect(...) should close on normal exit."""
    from dedalus_mcp.client import MCPClient

    fake_session = FakeClientSession()
    monkeypatch.setattr("dedalus_mcp.client.core.ClientSession", lambda *a, **kw: fake_session)

    async with await MCPClient.connect("http://localhost:8000/mcp", _transport_override=fake_session) as client:
        assert client.initialize_result is not None

    assert client._closed is True


@pytest.mark.anyio
async def test_context_manager_closes_on_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    """async with MCPClient.connect(...) should close even if exception raised."""
    from dedalus_mcp.client import MCPClient

    fake_session = FakeClientSession()
    monkeypatch.setattr("dedalus_mcp.client.core.ClientSession", lambda *a, **kw: fake_session)

    with pytest.raises(ValueError, match="test error"):
        async with await MCPClient.connect("http://localhost:8000/mcp", _transport_override=fake_session) as client:
            raise ValueError("test error")

    assert client._closed is True


@pytest.mark.anyio
async def test_reentry_on_closed_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Trying to use async with on an already-closed client should raise."""
    from dedalus_mcp.client import MCPClient

    fake_session = FakeClientSession()
    monkeypatch.setattr("dedalus_mcp.client.core.ClientSession", lambda *a, **kw: fake_session)

    client = await MCPClient.connect("http://localhost:8000/mcp", _transport_override=fake_session)
    await client.close()

    with pytest.raises(RuntimeError, match="closed|already"):
        async with client:
            pass


# ---------------------------------------------------------------------
# Phase 3: Transport Integration (integration tests, may need real server)
# ---------------------------------------------------------------------


# These tests are marked as integration tests and will be run separately
# with a real server when available.


# ---------------------------------------------------------------------
# Phase 4: Operations on Connected Client
# ---------------------------------------------------------------------


@pytest.mark.anyio
async def test_operations_raise_when_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Operations like ping() should raise after close()."""
    from dedalus_mcp.client import MCPClient

    fake_session = FakeClientSession()
    monkeypatch.setattr("dedalus_mcp.client.core.ClientSession", lambda *a, **kw: fake_session)

    client = await MCPClient.connect("http://localhost:8000/mcp", _transport_override=fake_session)
    await client.close()

    with pytest.raises(RuntimeError, match="closed|not connected"):
        await client.ping()
