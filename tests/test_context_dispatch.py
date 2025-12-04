# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Tests for Context.dispatch() integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock

import pytest

from dedalus_mcp.context import Context
from dedalus_mcp.dispatch import DirectDispatchBackend, DispatchRequest, DispatchResult
from dedalus_mcp.server.authorization import AuthorizationContext
from dedalus_mcp.server.services.connection_gate import ConnectionHandleNotAuthorizedError


@dataclass
class MockRequestContext:
    """Minimal mock for RequestContext."""

    request_id: str = "test-request-123"
    session: Any = None
    meta: Any = None
    lifespan_context: dict | None = None


class TestContextDispatch:
    """Tests for Context.dispatch() method."""

    @pytest.fixture
    def backend(self):
        """Create a DirectDispatchBackend with a mock driver."""
        backend = DirectDispatchBackend()

        async def mock_github_driver(intent: str, arguments: dict) -> dict:
            return {"intent": intent, "args": arguments, "status": "ok"}

        backend.register_driver("github", mock_github_driver)
        return backend

    @pytest.fixture
    def auth_context_with_handle(self):
        """Auth context that authorizes a specific handle."""
        return AuthorizationContext(
            subject="user123", scopes=["mcp:tools:call"], claims={"ddls:connections": ["ddls:conn:01ABC-github"]}
        )

    @pytest.fixture
    def context_with_backend(self, backend, auth_context_with_handle):
        """Context with dispatch backend configured."""
        mock_request_ctx = MockRequestContext(lifespan_context={"dedalus_mcp.runtime": {"dispatch_backend": backend}})
        mock_request = MagicMock()
        mock_request.scope = {"dedalus_mcp.auth": auth_context_with_handle}
        mock_request_ctx.request = mock_request

        ctx = Context(_request_context=mock_request_ctx, runtime={"dispatch_backend": backend})
        return ctx

    @pytest.mark.asyncio
    async def test_dispatch_authorized_handle_succeeds(self, context_with_backend):
        """Dispatch with authorized handle should succeed."""
        result = await context_with_backend.dispatch(
            connection_handle="ddls:conn:01ABC-github", intent="github:create_issue", arguments={"title": "Test"}
        )

        assert result.success is True
        assert result.data["intent"] == "github:create_issue"
        assert result.data["args"] == {"title": "Test"}

    @pytest.mark.asyncio
    async def test_dispatch_unauthorized_handle_rejected(self, context_with_backend):
        """Dispatch with unauthorized handle should be rejected."""
        with pytest.raises(ConnectionHandleNotAuthorizedError) as exc_info:
            await context_with_backend.dispatch(
                connection_handle="ddls:conn:99XYZ-slack",  # Not authorized
                intent="slack:post_message",
                arguments={},
            )

        assert "ddls:conn:99XYZ-slack" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_dispatch_no_backend_raises(self):
        """Dispatch without configured backend should raise."""
        mock_request_ctx = MockRequestContext()
        ctx = Context(_request_context=mock_request_ctx, runtime=None)

        with pytest.raises(RuntimeError, match="Dispatch backend not configured"):
            await ctx.dispatch(connection_handle="ddls:conn:01ABC-github", intent="github:create_issue", arguments={})

    @pytest.mark.asyncio
    async def test_dispatch_no_auth_context_skips_gate(self, backend):
        """Dispatch without auth context should skip gate check (OSS mode)."""
        mock_request_ctx = MockRequestContext()
        mock_request = MagicMock()
        mock_request.scope = {}  # No auth context
        mock_request_ctx.request = mock_request

        ctx = Context(_request_context=mock_request_ctx, runtime={"dispatch_backend": backend})

        # Should succeed without gate check
        result = await ctx.dispatch(
            connection_handle="ddls:conn:01ABC-github", intent="github:create_issue", arguments={"title": "Test"}
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_dispatch_default_empty_arguments(self, context_with_backend):
        """Dispatch should default to empty arguments dict."""
        result = await context_with_backend.dispatch(
            connection_handle="ddls:conn:01ABC-github", intent="github:list_repos"
        )

        assert result.success is True
        assert result.data["args"] == {}
