# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Tests for Context.dispatch() integration.

Authorization is handled by the enclave gateway at runtime. SDK only validates
handle format - it does not authorize handles locally.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock

import pytest

from dedalus_mcp.context import Context
from dedalus_mcp.dispatch import DirectDispatchBackend, HttpMethod, HttpRequest
from dedalus_mcp.server.authorization import AuthorizationContext
from dedalus_mcp.server.services.connection_gate import InvalidConnectionHandleError


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
        def mock_resolver(handle: str) -> tuple[str, str, str]:
            # Return (base_url, header_name, header_value) for test connections
            if "github" in handle:
                return ("https://api.github.com", "Authorization", "Bearer mock_github_token")
            elif "slack" in handle:
                return ("https://slack.com/api", "Authorization", "Bearer mock_slack_token")
            return ("https://example.com", "Authorization", "Bearer mock_token")

        backend = DirectDispatchBackend(credential_resolver=mock_resolver)
        return backend

    @pytest.fixture
    def auth_context(self):
        """Auth context with org reference (gateway validates connections)."""
        return AuthorizationContext(
            subject='user123',
            scopes=['mcp:tools:call'],
            claims={'ddls:org': 'org_123'},
        )

    @pytest.fixture
    def context_with_backend(self, backend, auth_context):
        """Context with dispatch backend configured."""
        mock_request_ctx = MockRequestContext(
            lifespan_context={'dedalus_mcp.runtime': {
                'dispatch_backend': backend,
                'connection_handles': {'github': 'ddls:conn:01ABC-github'}
            }}
        )
        mock_request = MagicMock()
        mock_request.scope = {'dedalus_mcp.auth': auth_context}
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
    async def test_dispatch_valid_handle_succeeds(self, context_with_backend):
        """Dispatch with valid handle format should succeed."""
        request = HttpRequest(method=HttpMethod.GET, path="/user")

        result = await context_with_backend.dispatch('github', request)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_dispatch_invalid_handle_format_rejected(self, backend, auth_context):
        """Dispatch with invalid handle format should be rejected."""
        mock_request_ctx = MockRequestContext(
            lifespan_context={'dedalus_mcp.runtime': {
                'dispatch_backend': backend,
                'connection_handles': {'invalid': 'not-a-valid-handle'}
            }}
        )
        mock_request = MagicMock()
        mock_request.scope = {'dedalus_mcp.auth': auth_context}
        mock_request_ctx.request = mock_request

        ctx = Context(
            _request_context=mock_request_ctx,
            runtime={
                'dispatch_backend': backend,
                'connection_handles': {'invalid': 'not-a-valid-handle'}
            }
        )
        request = HttpRequest(method=HttpMethod.POST, path="/api/test")

        with pytest.raises(InvalidConnectionHandleError) as exc_info:
            await ctx.dispatch('invalid', request)

        assert 'not-a-valid-handle' in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_dispatch_extracts_jwt_from_bearer_header(self, backend, auth_context):
        """Dispatch should extract JWT from Bearer Authorization header."""
        mock_request_ctx = MockRequestContext(
            lifespan_context={'dedalus_mcp.runtime': {
                'dispatch_backend': backend,
                'connection_handles': {'github': 'ddls:conn:01ABC-github'}
            }}
        )
        mock_request = MagicMock()
        mock_request.scope = {
            'dedalus_mcp.auth': auth_context,
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
    async def test_dispatch_extracts_jwt_from_dpop_header(self, backend, auth_context):
        """Dispatch should extract JWT from DPoP Authorization header."""
        mock_request_ctx = MockRequestContext(
            lifespan_context={'dedalus_mcp.runtime': {
                'dispatch_backend': backend,
                'connection_handles': {'github': 'ddls:conn:01ABC-github'}
            }}
        )
        mock_request = MagicMock()
        mock_request.scope = {
            'dedalus_mcp.auth': auth_context,
            'headers': [(b"authorization", b"DPoP test_jwt_token_xyz789")]
        }
        mock_request_ctx.request = mock_request

        ctx = Context(
            _request_context=mock_request_ctx,
            runtime={'dispatch_backend': backend, 'connection_handles': {'github': 'ddls:conn:01ABC-github'}}
        )
        request = HttpRequest(method=HttpMethod.GET, path="/repos")

        result = await ctx.dispatch('github', request)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_dispatch_dedalus_cloud_missing_jwt_raises(self, backend, auth_context, monkeypatch):
        """Dedalus Cloud dispatch without Authorization header should error."""
        monkeypatch.setenv("DEDALUS_DISPATCH_URL", "https://preview.enclave.dedaluslabs.ai")

        mock_request_ctx = MockRequestContext(
            lifespan_context={'dedalus_mcp.runtime': {
                'dispatch_backend': backend,
                'connection_handles': {'github': 'ddls:conn:01ABC-github'}
            }}
        )
        mock_request = MagicMock()
        mock_request.scope = {
            'dedalus_mcp.auth': auth_context,
            'headers': []  # No Authorization header
        }
        mock_request_ctx.request = mock_request

        ctx = Context(
            _request_context=mock_request_ctx,
            runtime={'dispatch_backend': backend, 'connection_handles': {'github': 'ddls:conn:01ABC-github'}}
        )
        request = HttpRequest(method=HttpMethod.GET, path="/user")

        with pytest.raises(RuntimeError, match='DEDALUS_DISPATCH_URL is set'):
            await ctx.dispatch('github', request)

    @pytest.mark.asyncio
    async def test_dispatch_no_backend_raises(self):
        """Dispatch without configured backend should raise."""
        mock_request_ctx = MockRequestContext()
        ctx = Context(_request_context=mock_request_ctx, runtime=None)
        request = HttpRequest(method=HttpMethod.POST, path="/repos")

        with pytest.raises(RuntimeError, match='Dispatch backend not configured'):
            await ctx.dispatch('ddls:conn:01ABC-github', request)

    @pytest.mark.asyncio
    async def test_dispatch_no_auth_context_still_validates_format(self, backend):
        """Dispatch without auth context should still validate handle format."""
        mock_request_ctx = MockRequestContext(
            lifespan_context={'dedalus_mcp.runtime': {
                'dispatch_backend': backend,
                'connection_handles': {'github': 'ddls:conn:01ABC-github'}
            }}
        )
        mock_request = MagicMock()
        mock_request.scope = {}  # No auth context
        mock_request_ctx.request = mock_request

        ctx = Context(
            _request_context=mock_request_ctx,
            runtime={'dispatch_backend': backend, 'connection_handles': {'github': 'ddls:conn:01ABC-github'}}
        )
        request = HttpRequest(method=HttpMethod.POST, path="/repos")

        # Valid handle should succeed
        result = await ctx.dispatch('github', request)
        assert result.success is True
