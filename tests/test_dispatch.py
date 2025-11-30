# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Tests for dispatch backend implementations.

The dispatch backend is the interface through which tools execute privileged
operations. It abstracts whether we're calling a real Enclave (EnclaveDispatchBackend)
or running in OSS mode with local credentials (DirectDispatchBackend).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest


# =============================================================================
# Test Data Models
# =============================================================================


@dataclass
class MockDispatchResult:
    """Mock result for testing."""

    success: bool
    data: dict[str, Any] | None = None
    error: str | None = None


# =============================================================================
# Protocol Tests
# =============================================================================


class TestDispatchRequestModel:
    """Tests for DispatchRequest data model."""

    def test_dispatch_request_construction(self):
        """DispatchRequest should hold connection_handle, intent, and arguments."""
        from openmcp.dispatch import DispatchRequest

        request = DispatchRequest(
            connection_handle="ddls:conn:01ABC-github",
            intent="github:create_issue",
            arguments={"title": "Bug", "body": "Description"},
        )

        assert request.connection_handle == "ddls:conn:01ABC-github"
        assert request.intent == "github:create_issue"
        assert request.arguments == {"title": "Bug", "body": "Description"}

    def test_dispatch_request_validation(self):
        """DispatchRequest should validate required fields."""
        from openmcp.dispatch import DispatchRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            DispatchRequest(
                connection_handle="",  # Empty
                intent="github:create_issue",
                arguments={},
            )


class TestDispatchResultModel:
    """Tests for DispatchResult data model."""

    def test_success_result(self):
        """Successful dispatch should have success=True and data."""
        from openmcp.dispatch import DispatchResult

        result = DispatchResult(
            success=True,
            data={"issue_number": 123},
        )

        assert result.success is True
        assert result.data == {"issue_number": 123}
        assert result.error is None

    def test_error_result(self):
        """Failed dispatch should have success=False and error message."""
        from openmcp.dispatch import DispatchResult

        result = DispatchResult(
            success=False,
            error="Connection refused",
        )

        assert result.success is False
        assert result.data is None
        assert result.error == "Connection refused"


class TestDispatchBackendProtocol:
    """Tests for DispatchBackend protocol compliance."""

    def test_backend_has_dispatch_method(self):
        """All backends should implement async dispatch() method."""
        from openmcp.dispatch import DispatchBackend, DispatchRequest, DispatchResult

        # Verify protocol defines the method
        import inspect

        assert hasattr(DispatchBackend, "dispatch")
        sig = inspect.signature(DispatchBackend.dispatch)
        assert "request" in sig.parameters


# =============================================================================
# DirectDispatchBackend Tests (OSS Mode)
# =============================================================================


class TestDirectDispatchBackend:
    """Tests for DirectDispatchBackend (OSS mode with local credentials)."""

    @pytest.mark.asyncio
    async def test_direct_dispatch_calls_driver(self):
        """Direct dispatch should invoke registered driver."""
        from openmcp.dispatch import DirectDispatchBackend, DispatchRequest

        # Register a mock driver
        calls = []

        async def mock_execute(intent: str, arguments: dict) -> dict:
            calls.append((intent, arguments))
            return {"result": "ok"}

        backend = DirectDispatchBackend()
        backend.register_driver("github", mock_execute)

        result = await backend.dispatch(
            DispatchRequest(
                connection_handle="ddls:conn_env_github_token",
                intent="github:create_issue",
                arguments={"title": "Test"},
            )
        )

        assert result.success is True
        assert result.data == {"result": "ok"}
        assert len(calls) == 1
        assert calls[0] == ("github:create_issue", {"title": "Test"})

    @pytest.mark.asyncio
    async def test_direct_dispatch_unknown_driver(self):
        """Dispatch to unknown driver should fail with clear error."""
        from openmcp.dispatch import DirectDispatchBackend, DispatchRequest

        backend = DirectDispatchBackend()

        result = await backend.dispatch(
            DispatchRequest(
                connection_handle="ddls:conn_env_unknown_service",
                intent="unknown:action",
                arguments={},
            )
        )

        assert result.success is False
        assert "driver" in result.error.lower() or "unknown" in result.error.lower()

    @pytest.mark.asyncio
    async def test_direct_dispatch_driver_exception(self):
        """Driver exceptions should be caught and returned as error result."""
        from openmcp.dispatch import DirectDispatchBackend, DispatchRequest

        async def failing_driver(intent: str, arguments: dict) -> dict:
            raise RuntimeError("API rate limited")

        backend = DirectDispatchBackend()
        backend.register_driver("github", failing_driver)

        result = await backend.dispatch(
            DispatchRequest(
                connection_handle="ddls:conn_env_github_token",
                intent="github:create_issue",
                arguments={},
            )
        )

        assert result.success is False
        assert "rate limited" in result.error.lower()


# =============================================================================
# EnclaveDispatchBackend Tests
# =============================================================================


class TestEnclaveDispatchBackend:
    """Tests for EnclaveDispatchBackend (calls real Enclave)."""

    @pytest.mark.asyncio
    async def test_enclave_dispatch_makes_http_request(self, respx_mock):
        """Enclave dispatch should POST to /dispatch with DPoP."""
        import httpx
        import respx

        from openmcp.dispatch import EnclaveDispatchBackend, DispatchRequest

        # Mock the enclave endpoint
        respx_mock.post("https://enclave.example.com/dispatch").mock(
            return_value=httpx.Response(
                200,
                json={"success": True, "data": {"created": True}},
            )
        )

        backend = EnclaveDispatchBackend(
            enclave_url="https://enclave.example.com",
            access_token="test_token",
        )

        result = await backend.dispatch(
            DispatchRequest(
                connection_handle="ddls:conn:01ABC-github",
                intent="github:create_issue",
                arguments={"title": "Test"},
            )
        )

        assert result.success is True
        assert result.data == {"created": True}

    @pytest.mark.asyncio
    async def test_enclave_dispatch_includes_dpop_header(self, respx_mock):
        """Enclave dispatch should include DPoP proof header when key provided."""
        import httpx

        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.backends import default_backend

        from openmcp.dispatch import EnclaveDispatchBackend, DispatchRequest

        # Generate ES256 key for DPoP
        dpop_key = ec.generate_private_key(ec.SECP256R1(), default_backend())

        captured_request = None

        def capture_request(request):
            nonlocal captured_request
            captured_request = request
            return httpx.Response(200, json={"success": True})

        respx_mock.post("https://enclave.example.com/dispatch").mock(
            side_effect=capture_request
        )

        backend = EnclaveDispatchBackend(
            enclave_url="https://enclave.example.com",
            access_token="test_token",
            dpop_key=dpop_key,
        )

        await backend.dispatch(
            DispatchRequest(
                connection_handle="ddls:conn:01ABC-github",
                intent="github:create_issue",
                arguments={},
            )
        )

        assert captured_request is not None
        assert "DPoP" in captured_request.headers.get("Authorization", "")
        assert "dpop" in captured_request.headers  # The proof header (lowercase)

    @pytest.mark.asyncio
    async def test_enclave_dispatch_handles_401(self, respx_mock):
        """401 from enclave should result in auth error."""
        import httpx

        from openmcp.dispatch import EnclaveDispatchBackend, DispatchRequest

        respx_mock.post("https://enclave.example.com/dispatch").mock(
            return_value=httpx.Response(401, json={"error": "token_expired"})
        )

        backend = EnclaveDispatchBackend(
            enclave_url="https://enclave.example.com",
            access_token="expired_token",
        )

        result = await backend.dispatch(
            DispatchRequest(
                connection_handle="ddls:conn:01ABC-github",
                intent="github:create_issue",
                arguments={},
            )
        )

        assert result.success is False
        assert "auth" in result.error.lower() or "401" in result.error

    @pytest.mark.asyncio
    async def test_enclave_dispatch_handles_timeout(self, respx_mock):
        """Timeout should be handled gracefully."""
        import httpx

        from openmcp.dispatch import EnclaveDispatchBackend, DispatchRequest

        respx_mock.post("https://enclave.example.com/dispatch").mock(
            side_effect=httpx.TimeoutException("timeout")
        )

        backend = EnclaveDispatchBackend(
            enclave_url="https://enclave.example.com",
            access_token="test_token",
        )

        result = await backend.dispatch(
            DispatchRequest(
                connection_handle="ddls:conn:01ABC-github",
                intent="github:create_issue",
                arguments={},
            )
        )

        assert result.success is False
        assert "timed out" in result.error.lower()


# =============================================================================
# Integration Tests
# =============================================================================


class TestDispatchIntegration:
    """Integration tests for dispatch flow."""

    @pytest.mark.asyncio
    async def test_dispatch_with_connection_gate(self):
        """Dispatch should check connection gate before forwarding."""
        from openmcp.dispatch import DirectDispatchBackend, DispatchRequest
        from openmcp.server.services.connection_gate import ConnectionHandleGate

        backend = DirectDispatchBackend()
        gate = ConnectionHandleGate(authorized_handles={"ddls:conn_env_github_token"})

        # Authorized handle should work
        gate.check("ddls:conn_env_github_token")  # No raise

        # Unauthorized should fail before dispatch
        from openmcp.server.services.connection_gate import ConnectionHandleNotAuthorizedError

        with pytest.raises(ConnectionHandleNotAuthorizedError):
            gate.check("ddls:conn:unauthorized-handle")

