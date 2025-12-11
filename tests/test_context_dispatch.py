# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Tests for Context.dispatch() integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock

import pytest

from dedalus_mcp.context import Context
from dedalus_mcp.dispatch import DirectDispatchBackend, DispatchResponse, HttpMethod, HttpRequest
from dedalus_mcp.server.authorization import AuthorizationContext
from dedalus_mcp.server.services.connection_gate import (
    ConnectionHandleNotAuthorizedError,
)


@dataclass
class MockRequestContext:
    """Minimal mock for RequestContext."""

    request_id: str = 'test-request-123'
    session: Any = None
    meta: Any = None
    lifespan_context: dict | None = None


class TestContextDispatch:
    """Tests for Context.dispatch() method."""

    @pytest.fixture
    def backend(self):
        """Create a DirectDispatchBackend with a mock resolver."""
        def mock_resolver(handle: str) -> tuple[str, str]:
            # Return (base_url, auth_header) for test connections
            if "github" in handle:
                return ("https://api.github.com", "Bearer mock_github_token")
            elif "slack" in handle:
                return ("https://slack.com/api", "Bearer mock_slack_token")
            return ("https://example.com", "Bearer mock_token")

        backend = DirectDispatchBackend(credential_resolver=mock_resolver)
        return backend

    @pytest.fixture
    def auth_context_with_handle(self):
        """Auth context that authorizes a specific handle."""
        return AuthorizationContext(
            subject='user123',
            scopes=['mcp:tools:call'],
            claims={'ddls:connections': [
                {'id': 'ddls:conn:01ABC-github', 'name': 'github'}
            ]},
        )

    @pytest.fixture
    def context_with_backend(self, backend, auth_context_with_handle):
        """Context with dispatch backend configured."""
        mock_request_ctx = MockRequestContext(
            lifespan_context={'dedalus_mcp.runtime': {
                'dispatch_backend': backend,
                'connection_handles': {'github': 'ddls:conn:01ABC-github'}
            }}
        )
        mock_request = MagicMock()
        mock_request.scope = {'dedalus_mcp.auth': auth_context_with_handle}
        mock_request_ctx.request = mock_request

        ctx = Context(
            _request_context=mock_request_ctx,
            runtime={
                'dispatch_backend': backend,
                'connection_handles': {'github': 'ddls:conn:01ABC-github'}
            }
        )
        return ctx

    @pytest.mark.asyncio
    async def test_dispatch_authorized_handle_succeeds(self, context_with_backend):
        """Dispatch with authorized handle should succeed."""
        request = HttpRequest(method=HttpMethod.GET, path="/user")

        result = await context_with_backend.dispatch('github', request)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_dispatch_unauthorized_handle_rejected(self, context_with_backend):
        """Dispatch with unauthorized handle should be rejected."""
        request = HttpRequest(method=HttpMethod.POST, path="/api/chat.postMessage")

        with pytest.raises(ConnectionHandleNotAuthorizedError) as exc_info:
            await context_with_backend.dispatch('ddls:conn:99XYZ-slack', request)

        assert 'ddls:conn:99XYZ-slack' in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_dispatch_extracts_jwt_from_bearer_header(self, backend, auth_context_with_handle):
        """Dispatch should extract JWT from Bearer Authorization header."""
        mock_request_ctx = MockRequestContext(
            lifespan_context={'dedalus_mcp.runtime': {
                'dispatch_backend': backend,
                'connection_handles': {'github': 'ddls:conn:01ABC-github'}
            }}
        )
        mock_request = MagicMock()
        mock_request.scope = {
            'dedalus_mcp.auth': auth_context_with_handle,
            'headers': [(b"authorization", b"Bearer test_jwt_token_abc123")]
        }
        mock_request_ctx.request = mock_request

        ctx = Context(
            _request_context=mock_request_ctx,
            runtime={'dispatch_backend': backend, 'connection_handles': {'github': 'ddls:conn:01ABC-github'}}
        )
        request = HttpRequest(method=HttpMethod.GET, path="/user")

        result = await ctx.dispatch('github', request)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_dispatch_extracts_jwt_from_dpop_header(self, backend, auth_context_with_handle):
        """Dispatch should extract JWT from DPoP Authorization header."""
        mock_request_ctx = MockRequestContext(
            lifespan_context={'dedalus_mcp.runtime': {'dispatch_backend': backend}}
        )
        mock_request = MagicMock()
        mock_request.scope = {
            'dedalus_mcp.auth': auth_context_with_handle,
            'headers': [(b"authorization", b"DPoP test_jwt_token_xyz789")]
        }
        mock_request_ctx.request = mock_request

        ctx = Context(_request_context=mock_request_ctx, runtime={'dispatch_backend': backend})
        request = HttpRequest(method=HttpMethod.GET, path="/repos")

        result = await ctx.dispatch('ddls:conn:01ABC-github', request)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_dispatch_dedalus_cloud_missing_jwt_raises(self, backend, auth_context_with_handle, monkeypatch):
        """Dedalus Cloud dispatch without Authorization header should error."""
        monkeypatch.setenv("DEDALUS_DISPATCH_URL", "https://preview.enclave.dedaluslabs.ai")

        mock_request_ctx = MockRequestContext(
            lifespan_context={'dedalus_mcp.runtime': {'dispatch_backend': backend}}
        )
        mock_request = MagicMock()
        mock_request.scope = {
            'dedalus_mcp.auth': auth_context_with_handle,
            'headers': []  # No Authorization header
        }
        mock_request_ctx.request = mock_request

        ctx = Context(_request_context=mock_request_ctx, runtime={'dispatch_backend': backend})
        request = HttpRequest(method=HttpMethod.GET, path="/user")

        with pytest.raises(RuntimeError, match='Expected Authorization header'):
            await ctx.dispatch('ddls:conn:01ABC-github', request)

    @pytest.mark.asyncio
    async def test_dispatch_no_backend_raises(self):
        """Dispatch without configured backend should raise."""
        mock_request_ctx = MockRequestContext()
        ctx = Context(_request_context=mock_request_ctx, runtime=None)
        request = HttpRequest(method=HttpMethod.POST, path="/repos")

        with pytest.raises(RuntimeError, match='Dispatch backend not configured'):
            await ctx.dispatch('ddls:conn:01ABC-github', request)

    @pytest.mark.asyncio
    async def test_dispatch_no_auth_context_skips_gate(self, backend):
        """Dispatch without auth context should skip gate check (OSS mode)."""
        mock_request_ctx = MockRequestContext()
        mock_request = MagicMock()
        mock_request.scope = {}  # No auth context
        mock_request_ctx.request = mock_request

        ctx = Context(
            _request_context=mock_request_ctx, runtime={'dispatch_backend': backend}
        )
        request = HttpRequest(method=HttpMethod.POST, path="/repos")

        # Should succeed without gate check
        result = await ctx.dispatch('ddls:conn:01ABC-github', request)

        assert result.success is True
