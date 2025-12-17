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


class TestDispatchWireRequestModel:
    """Tests for DispatchWireRequest data model."""

    def test_wire_request_construction(self):
        """DispatchWireRequest should hold connection_handle and HttpRequest."""
        from dedalus_mcp.dispatch import DispatchWireRequest, HttpMethod, HttpRequest

        http_req = HttpRequest(
            method=HttpMethod.POST,
            path="/repos/owner/repo/issues",
            body={"title": "Bug", "body": "Description"},
        )
        request = DispatchWireRequest(
            connection_handle="ddls:conn:01ABC-github",
            request=http_req,
        )

        assert request.connection_handle == "ddls:conn:01ABC-github"
        assert request.request.method == HttpMethod.POST
        assert request.request.path == "/repos/owner/repo/issues"

    def test_wire_request_validation(self):
        """DispatchWireRequest should validate handle format."""
        from dedalus_mcp.dispatch import DispatchWireRequest, HttpMethod, HttpRequest
        from pydantic import ValidationError

        http_req = HttpRequest(method=HttpMethod.GET, path="/user")

        with pytest.raises(ValidationError):
            DispatchWireRequest(
                connection_handle="invalid-format",  # Must start with ddls:conn
                request=http_req,
            )


class TestDispatchResponseModel:
    """Tests for DispatchResponse data model."""

    def test_success_response(self):
        """Successful dispatch should have success=True and HttpResponse."""
        from dedalus_mcp.dispatch import DispatchResponse, HttpResponse

        http_resp = HttpResponse(status=200, body={"issue_number": 123})
        result = DispatchResponse.ok(http_resp)

        assert result.success is True
        assert result.response.status == 200
        assert result.response.body == {"issue_number": 123}
        assert result.error is None

    def test_error_response(self):
        """Failed dispatch should have success=False and DispatchError."""
        from dedalus_mcp.dispatch import DispatchErrorCode, DispatchResponse

        result = DispatchResponse.fail(
            DispatchErrorCode.DOWNSTREAM_UNREACHABLE,
            "Connection refused",
            retryable=True,
        )

        assert result.success is False
        assert result.response is None
        assert result.error.code == DispatchErrorCode.DOWNSTREAM_UNREACHABLE
        assert result.error.message == "Connection refused"
        assert result.error.retryable is True


class TestDispatchBackendProtocol:
    """Tests for DispatchBackend protocol compliance."""

    def test_backend_has_dispatch_method(self):
        """All backends should implement async dispatch() method."""
        from dedalus_mcp.dispatch import DispatchBackend

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
    async def test_direct_dispatch_with_resolver(self, respx_mock):
        """Direct dispatch should use credential resolver and make HTTP request."""
        import httpx

        from dedalus_mcp.dispatch import (
            DirectDispatchBackend,
            DispatchWireRequest,
            HttpMethod,
            HttpRequest,
        )

        # Mock the downstream API
        respx_mock.get("https://api.github.com/user").mock(
            return_value=httpx.Response(200, json={"login": "testuser"})
        )

        # Credential resolver returns (base_url, header_name, header_value)
        def resolver(handle: str) -> tuple[str, str, str]:
            return ("https://api.github.com", "Authorization", "Bearer test_token")

        backend = DirectDispatchBackend(credential_resolver=resolver)

        result = await backend.dispatch(
            DispatchWireRequest(
                connection_handle="ddls:conn:github",
                request=HttpRequest(method=HttpMethod.GET, path="/user"),
            )
        )

        assert result.success is True
        assert result.response.status == 200
        assert result.response.body == {"login": "testuser"}

    @pytest.mark.asyncio
    async def test_direct_dispatch_no_resolver(self):
        """Dispatch without credential resolver should fail."""
        from dedalus_mcp.dispatch import (
            DirectDispatchBackend,
            DispatchWireRequest,
            HttpMethod,
            HttpRequest,
        )

        backend = DirectDispatchBackend(credential_resolver=None)

        result = await backend.dispatch(
            DispatchWireRequest(
                connection_handle="ddls:conn:github",
                request=HttpRequest(method=HttpMethod.GET, path="/user"),
            )
        )

        assert result.success is False
        assert "credential resolver" in result.error.message.lower()

    @pytest.mark.asyncio
    async def test_direct_dispatch_resolver_exception(self):
        """Resolver exceptions should be caught and returned as error."""
        from dedalus_mcp.dispatch import (
            DirectDispatchBackend,
            DispatchWireRequest,
            HttpMethod,
            HttpRequest,
        )

        def failing_resolver(handle: str) -> tuple[str, str, str]:
            raise RuntimeError("Credentials not found")

        backend = DirectDispatchBackend(credential_resolver=failing_resolver)

        result = await backend.dispatch(
            DispatchWireRequest(
                connection_handle="ddls:conn:github",
                request=HttpRequest(method=HttpMethod.GET, path="/user"),
            )
        )

        assert result.success is False
        assert "credentials not found" in result.error.message.lower()


# =============================================================================
# EnclaveDispatchBackend Tests
# =============================================================================


class TestEnclaveDispatchBackend:
    """Tests for EnclaveDispatchBackend (calls real Enclave)."""

    @pytest.mark.asyncio
    async def test_enclave_dispatch_makes_http_request(self, respx_mock):
        """Enclave dispatch should POST to /dispatch with response envelope."""
        import httpx

        from dedalus_mcp.dispatch import (
            EnclaveDispatchBackend,
            DispatchWireRequest,
            HttpMethod,
            HttpRequest,
        )

        # Mock the enclave endpoint - returns DispatchResponse envelope
        respx_mock.post("https://enclave.example.com/dispatch").mock(
            return_value=httpx.Response(
                200,
                json={
                    "success": True,
                    "response": {"status": 201, "headers": {}, "body": {"created": True}},
                },
            )
        )

        backend = EnclaveDispatchBackend(
            enclave_url="https://enclave.example.com",
            access_token="test_token",
        )

        result = await backend.dispatch(
            DispatchWireRequest(
                connection_handle="ddls:conn:01ABC-github",
                request=HttpRequest(
                    method=HttpMethod.POST,
                    path="/repos/owner/repo/issues",
                    body={"title": "Test"},
                ),
            )
        )

        assert result.success is True
        assert result.response.status == 201
        assert result.response.body == {"created": True}

    @pytest.mark.asyncio
    async def test_enclave_dispatch_includes_dpop_header(self, respx_mock):
        """Enclave dispatch should include DPoP proof header when key provided."""
        import httpx
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives.asymmetric import ec

        from dedalus_mcp.dispatch import (
            EnclaveDispatchBackend,
            DispatchWireRequest,
            HttpMethod,
            HttpRequest,
        )

        # Generate ES256 key for DPoP
        dpop_key = ec.generate_private_key(ec.SECP256R1(), default_backend())

        captured_request = None

        def capture_request(request):
            nonlocal captured_request
            captured_request = request
            return httpx.Response(
                200,
                json={"success": True, "response": {"status": 201, "headers": {}, "body": {}}},
            )

        respx_mock.post("https://enclave.example.com/dispatch").mock(side_effect=capture_request)

        backend = EnclaveDispatchBackend(
            enclave_url="https://enclave.example.com",
            access_token="test_token",
            dpop_key=dpop_key,
        )

        await backend.dispatch(
            DispatchWireRequest(
                connection_handle="ddls:conn:01ABC-github",
                request=HttpRequest(method=HttpMethod.POST, path="/repos/owner/repo/issues", body={}),
            )
        )

        assert captured_request is not None
        assert "DPoP" in captured_request.headers.get("Authorization", "")
        assert "DPoP" in captured_request.headers  # The proof header

    @pytest.mark.asyncio
    async def test_enclave_dispatch_handles_401(self, respx_mock):
        """401 from enclave should result in auth error."""
        import httpx

        from dedalus_mcp.dispatch import (
            EnclaveDispatchBackend,
            DispatchWireRequest,
            HttpMethod,
            HttpRequest,
        )

        respx_mock.post("https://enclave.example.com/dispatch").mock(
            return_value=httpx.Response(401, json={"error": "token_expired"})
        )

        backend = EnclaveDispatchBackend(
            enclave_url="https://enclave.example.com",
            access_token="expired_token",
        )

        result = await backend.dispatch(
            DispatchWireRequest(
                connection_handle="ddls:conn:01ABC-github",
                request=HttpRequest(method=HttpMethod.POST, path="/issues", body={}),
            )
        )

        assert result.success is False
        assert "auth" in result.error.message.lower() or "401" in result.error.message

    @pytest.mark.asyncio
    async def test_enclave_dispatch_handles_timeout(self, respx_mock):
        """Timeout should be handled gracefully."""
        import httpx

        from dedalus_mcp.dispatch import (
            EnclaveDispatchBackend,
            DispatchWireRequest,
            HttpMethod,
            HttpRequest,
        )

        respx_mock.post("https://enclave.example.com/dispatch").mock(
            side_effect=httpx.TimeoutException("timeout")
        )

        backend = EnclaveDispatchBackend(
            enclave_url="https://enclave.example.com",
            access_token="test_token",
        )

        result = await backend.dispatch(
            DispatchWireRequest(
                connection_handle="ddls:conn:01ABC-github",
                request=HttpRequest(method=HttpMethod.POST, path="/issues", body={}),
            )
        )

        assert result.success is False
        assert "timed out" in result.error.message.lower()


# =============================================================================
# Integration Tests
# =============================================================================


class TestHttpRequestValidation:
    """Tests for HttpRequest validation."""

    def test_path_must_start_with_slash(self):
        """Path must start with /."""
        from dedalus_mcp.dispatch import HttpMethod, HttpRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="path must start with"):
            HttpRequest(method=HttpMethod.GET, path="user")

    def test_headers_allowed(self):
        """Non-auth headers are allowed."""
        from dedalus_mcp.dispatch import HttpMethod, HttpRequest

        req = HttpRequest(
            method=HttpMethod.GET,
            path="/user",
            headers={"apikey": "key123", "Accept": "application/json"},
        )
        assert req.headers["apikey"] == "key123"


class TestDirectDispatchBackendHTTPErrors:
    """Tests for DirectDispatchBackend HTTP error handling."""

    @pytest.mark.asyncio
    async def test_dispatch_4xx_response(self, respx_mock):
        """4xx responses should return success=True with error status."""
        import httpx

        from dedalus_mcp.dispatch import (
            DirectDispatchBackend,
            DispatchWireRequest,
            HttpMethod,
            HttpRequest,
        )

        respx_mock.get("https://api.github.com/user").mock(
            return_value=httpx.Response(404, json={"message": "Not found"})
        )

        def resolver(handle: str) -> tuple[str, str, str]:
            return ("https://api.github.com", "Authorization", "Bearer test_token")

        backend = DirectDispatchBackend(credential_resolver=resolver)
        result = await backend.dispatch(
            DispatchWireRequest(
                connection_handle="ddls:conn:github",
                request=HttpRequest(method=HttpMethod.GET, path="/user"),
            )
        )

        assert result.success is True
        assert result.response.status == 404
        assert result.response.body == {"message": "Not found"}

    @pytest.mark.asyncio
    async def test_dispatch_5xx_response(self, respx_mock):
        """5xx responses should return success=True with error status."""
        import httpx

        from dedalus_mcp.dispatch import (
            DirectDispatchBackend,
            DispatchWireRequest,
            HttpMethod,
            HttpRequest,
        )

        respx_mock.post("https://api.service.com/endpoint").mock(
            return_value=httpx.Response(503, text="Service unavailable")
        )

        def resolver(handle: str) -> tuple[str, str, str]:
            return ("https://api.service.com", "Authorization", "Bearer token")

        backend = DirectDispatchBackend(credential_resolver=resolver)
        result = await backend.dispatch(
            DispatchWireRequest(
                connection_handle="ddls:conn:service",
                request=HttpRequest(method=HttpMethod.POST, path="/endpoint", body={}),
            )
        )

        assert result.success is True
        assert result.response.status == 503
        assert result.response.body == "Service unavailable"

    @pytest.mark.asyncio
    async def test_dispatch_non_json_response(self, respx_mock):
        """Non-JSON responses should be returned as text."""
        import httpx

        from dedalus_mcp.dispatch import (
            DirectDispatchBackend,
            DispatchWireRequest,
            HttpMethod,
            HttpRequest,
        )

        respx_mock.get("https://api.example.com/health").mock(
            return_value=httpx.Response(200, text="OK", headers={"content-type": "text/plain"})
        )

        def resolver(handle: str) -> tuple[str, str, str]:
            return ("https://api.example.com", "Authorization", "Bearer token")

        backend = DirectDispatchBackend(credential_resolver=resolver)
        result = await backend.dispatch(
            DispatchWireRequest(
                connection_handle="ddls:conn:api",
                request=HttpRequest(method=HttpMethod.GET, path="/health"),
            )
        )

        assert result.success is True
        assert result.response.body == "OK"

    @pytest.mark.asyncio
    async def test_dispatch_connect_error(self, respx_mock):
        """Connection errors should return retryable failure."""
        import httpx

        from dedalus_mcp.dispatch import (
            DirectDispatchBackend,
            DispatchWireRequest,
            HttpMethod,
            HttpRequest,
        )

        respx_mock.get("https://api.offline.com/endpoint").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        def resolver(handle: str) -> tuple[str, str, str]:
            return ("https://api.offline.com", "Authorization", "Bearer token")

        backend = DirectDispatchBackend(credential_resolver=resolver)
        result = await backend.dispatch(
            DispatchWireRequest(
                connection_handle="ddls:conn:offline",
                request=HttpRequest(method=HttpMethod.GET, path="/endpoint"),
            )
        )

        assert result.success is False
        assert result.error.code.value == "DOWNSTREAM_UNREACHABLE"
        assert result.error.retryable is True
        assert "connect" in result.error.message.lower()

    @pytest.mark.asyncio
    async def test_dispatch_timeout(self, respx_mock):
        """Timeout errors should return retryable failure."""
        import httpx

        from dedalus_mcp.dispatch import (
            DirectDispatchBackend,
            DispatchWireRequest,
            HttpMethod,
            HttpRequest,
        )

        respx_mock.get("https://api.slow.com/endpoint").mock(side_effect=httpx.TimeoutException("timeout"))

        def resolver(handle: str) -> tuple[str, str, str]:
            return ("https://api.slow.com", "Authorization", "Bearer token")

        backend = DirectDispatchBackend(credential_resolver=resolver)
        result = await backend.dispatch(
            DispatchWireRequest(
                connection_handle="ddls:conn:slow",
                request=HttpRequest(method=HttpMethod.GET, path="/endpoint", timeout_ms=5000),
            )
        )

        assert result.success is False
        assert result.error.code.value == "DOWNSTREAM_TIMEOUT"
        assert result.error.retryable is True
        assert "timed out" in result.error.message.lower()

    @pytest.mark.asyncio
    async def test_dispatch_with_custom_headers(self, respx_mock):
        """Custom non-auth headers should be forwarded."""
        import httpx

        from dedalus_mcp.dispatch import (
            DirectDispatchBackend,
            DispatchWireRequest,
            HttpMethod,
            HttpRequest,
        )

        captured = None

        def capture(request):
            nonlocal captured
            captured = request
            return httpx.Response(200, json={})

        respx_mock.get("https://api.github.com/repos/owner/repo").mock(side_effect=capture)

        def resolver(handle: str) -> tuple[str, str, str]:
            return ("https://api.github.com", "Authorization", "Bearer token")

        backend = DirectDispatchBackend(credential_resolver=resolver)
        await backend.dispatch(
            DispatchWireRequest(
                connection_handle="ddls:conn:github",
                request=HttpRequest(
                    method=HttpMethod.GET,
                    path="/repos/owner/repo",
                    headers={"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"},
                ),
            )
        )

        assert captured is not None
        assert captured.headers["Accept"] == "application/vnd.github+json"
        assert captured.headers["X-GitHub-Api-Version"] == "2022-11-28"
        assert "Authorization" in captured.headers

    @pytest.mark.asyncio
    async def test_dispatch_with_string_body(self, respx_mock):
        """String body should be sent as content, not JSON."""
        import httpx

        from dedalus_mcp.dispatch import (
            DirectDispatchBackend,
            DispatchWireRequest,
            HttpMethod,
            HttpRequest,
        )

        captured = None

        def capture(request):
            nonlocal captured
            captured = request
            return httpx.Response(200, text="OK")

        respx_mock.post("https://api.example.com/webhook").mock(side_effect=capture)

        def resolver(handle: str) -> tuple[str, str, str]:
            return ("https://api.example.com", "Authorization", "Bearer token")

        backend = DirectDispatchBackend(credential_resolver=resolver)
        await backend.dispatch(
            DispatchWireRequest(
                connection_handle="ddls:conn:api",
                request=HttpRequest(method=HttpMethod.POST, path="/webhook", body="raw text payload"),
            )
        )

        assert captured is not None
        assert captured.content == b"raw text payload"

    @pytest.mark.asyncio
    async def test_dispatch_malformed_json_response(self, respx_mock):
        """Malformed JSON should fallback to text."""
        import httpx

        from dedalus_mcp.dispatch import (
            DirectDispatchBackend,
            DispatchWireRequest,
            HttpMethod,
            HttpRequest,
        )

        respx_mock.get("https://api.example.com/endpoint").mock(
            return_value=httpx.Response(
                200,
                text="{invalid json",
                headers={"content-type": "application/json"},
            )
        )

        def resolver(handle: str) -> tuple[str, str, str]:
            return ("https://api.example.com", "Authorization", "Bearer token")

        backend = DirectDispatchBackend(credential_resolver=resolver)
        result = await backend.dispatch(
            DispatchWireRequest(
                connection_handle="ddls:conn:api",
                request=HttpRequest(method=HttpMethod.GET, path="/endpoint"),
            )
        )

        assert result.success is True
        assert result.response.body == "{invalid json"


class TestEnclaveDispatchBackendAdvanced:
    """Advanced tests for EnclaveDispatchBackend."""

    @pytest.mark.asyncio
    async def test_enclave_dispatch_with_hmac_signature(self, respx_mock):
        """Enclave dispatch should include HMAC signature when deployment auth configured."""
        import base64
        import httpx

        from dedalus_mcp.dispatch import (
            EnclaveDispatchBackend,
            DispatchWireRequest,
            HttpMethod,
            HttpRequest,
        )

        captured = None

        def capture(request):
            nonlocal captured
            captured = request
            return httpx.Response(
                200,
                json={"success": True, "response": {"status": 200, "headers": {}, "body": {}}},
            )

        respx_mock.post("https://enclave.example.com/dispatch").mock(side_effect=capture)

        auth_secret = base64.b64encode(b"0" * 32)
        backend = EnclaveDispatchBackend(
            enclave_url="https://enclave.example.com",
            access_token="test_token",
            deployment_id="dep_01ABC",
            auth_secret=base64.b64decode(auth_secret),
        )

        await backend.dispatch(
            DispatchWireRequest(
                connection_handle="ddls:conn:github",
                request=HttpRequest(method=HttpMethod.GET, path="/user"),
            )
        )

        assert captured is not None
        assert "X-Dedalus-Timestamp" in captured.headers
        assert "X-Dedalus-Deployment" in captured.headers
        assert captured.headers["X-Dedalus-Deployment"] == "dep_01ABC"
        assert "X-Dedalus-Signature" in captured.headers

    @pytest.mark.asyncio
    async def test_enclave_dispatch_handles_403(self, respx_mock):
        """403 from enclave should result in authorization error."""
        import httpx

        from dedalus_mcp.dispatch import (
            EnclaveDispatchBackend,
            DispatchWireRequest,
            HttpMethod,
            HttpRequest,
        )

        respx_mock.post("https://enclave.example.com/dispatch").mock(
            return_value=httpx.Response(403, json={"error": "forbidden"})
        )

        backend = EnclaveDispatchBackend(
            enclave_url="https://enclave.example.com",
            access_token="test_token",
        )

        result = await backend.dispatch(
            DispatchWireRequest(
                connection_handle="ddls:conn:github",
                request=HttpRequest(method=HttpMethod.GET, path="/user"),
            )
        )

        assert result.success is False
        assert result.error.code.value == "CONNECTION_NOT_FOUND"
        assert "403" in result.error.message

    @pytest.mark.asyncio
    async def test_enclave_dispatch_handles_500(self, respx_mock):
        """5xx from enclave should result in downstream error."""
        import httpx

        from dedalus_mcp.dispatch import (
            EnclaveDispatchBackend,
            DispatchWireRequest,
            HttpMethod,
            HttpRequest,
        )

        respx_mock.post("https://enclave.example.com/dispatch").mock(
            return_value=httpx.Response(500, text="Internal server error")
        )

        backend = EnclaveDispatchBackend(
            enclave_url="https://enclave.example.com",
            access_token="test_token",
        )

        result = await backend.dispatch(
            DispatchWireRequest(
                connection_handle="ddls:conn:github",
                request=HttpRequest(method=HttpMethod.GET, path="/user"),
            )
        )

        assert result.success is False
        assert result.error.code.value == "DOWNSTREAM_UNREACHABLE"
        assert "500" in result.error.message

    @pytest.mark.asyncio
    async def test_enclave_dispatch_error_response(self, respx_mock):
        """Enclave error responses should be properly handled."""
        import httpx

        from dedalus_mcp.dispatch import (
            EnclaveDispatchBackend,
            DispatchWireRequest,
            HttpMethod,
            HttpRequest,
        )

        respx_mock.post("https://enclave.example.com/dispatch").mock(
            return_value=httpx.Response(
                200,
                json={
                    "success": False,
                    "error": {
                        "code": "DOWNSTREAM_TIMEOUT",
                        "message": "Request timed out",
                        "retryable": True,
                    },
                },
            )
        )

        backend = EnclaveDispatchBackend(
            enclave_url="https://enclave.example.com",
            access_token="test_token",
        )

        result = await backend.dispatch(
            DispatchWireRequest(
                connection_handle="ddls:conn:github",
                request=HttpRequest(method=HttpMethod.GET, path="/user"),
            )
        )

        assert result.success is False
        assert result.error.code.value == "DOWNSTREAM_TIMEOUT"
        assert result.error.message == "Request timed out"
        assert result.error.retryable is True

    @pytest.mark.asyncio
    async def test_enclave_dispatch_network_error(self, respx_mock):
        """Network errors should be handled gracefully."""
        import httpx

        from dedalus_mcp.dispatch import (
            EnclaveDispatchBackend,
            DispatchWireRequest,
            HttpMethod,
            HttpRequest,
        )

        respx_mock.post("https://enclave.example.com/dispatch").mock(
            side_effect=httpx.RequestError("Network error")
        )

        backend = EnclaveDispatchBackend(
            enclave_url="https://enclave.example.com",
            access_token="test_token",
        )

        result = await backend.dispatch(
            DispatchWireRequest(
                connection_handle="ddls:conn:github",
                request=HttpRequest(method=HttpMethod.GET, path="/user"),
            )
        )

        assert result.success is False
        assert result.error.code.value == "DOWNSTREAM_UNREACHABLE"
        assert result.error.retryable is True

    @pytest.mark.asyncio
    async def test_enclave_dispatch_bearer_auth_fallback(self, respx_mock):
        """Without DPoP key, should use Bearer auth."""
        import httpx

        from dedalus_mcp.dispatch import (
            EnclaveDispatchBackend,
            DispatchWireRequest,
            HttpMethod,
            HttpRequest,
        )

        captured = None

        def capture(request):
            nonlocal captured
            captured = request
            return httpx.Response(
                200,
                json={"success": True, "response": {"status": 200, "headers": {}, "body": {}}},
            )

        respx_mock.post("https://enclave.example.com/dispatch").mock(side_effect=capture)

        backend = EnclaveDispatchBackend(
            enclave_url="https://enclave.example.com",
            access_token="test_token",
            dpop_key=None,
        )

        await backend.dispatch(
            DispatchWireRequest(
                connection_handle="ddls:conn:github",
                request=HttpRequest(method=HttpMethod.GET, path="/user"),
            )
        )

        assert captured is not None
        assert captured.headers["Authorization"] == "Bearer test_token"
        assert "DPoP" not in captured.headers


class TestHttpRequestEdgeCases:
    """Edge case tests for HttpRequest."""

    def test_headers_none_allowed(self):
        """None headers should be allowed."""
        from dedalus_mcp.dispatch import HttpMethod, HttpRequest

        req = HttpRequest(method=HttpMethod.GET, path="/user", headers=None)
        assert req.headers is None


class TestDirectDispatchBackendEdgeCases:
    """Edge case tests for DirectDispatchBackend."""

    @pytest.mark.asyncio
    async def test_dispatch_unexpected_exception(self, respx_mock):
        """Unexpected exceptions should be caught and logged."""
        import httpx

        from dedalus_mcp.dispatch import (
            DirectDispatchBackend,
            DispatchWireRequest,
            HttpMethod,
            HttpRequest,
        )

        respx_mock.get("https://api.example.com/endpoint").mock(
            side_effect=RuntimeError("Unexpected error in httpx")
        )

        def resolver(handle: str) -> tuple[str, str, str]:
            return ("https://api.example.com", "Authorization", "Bearer token")

        backend = DirectDispatchBackend(credential_resolver=resolver)
        result = await backend.dispatch(
            DispatchWireRequest(
                connection_handle="ddls:conn:api",
                request=HttpRequest(method=HttpMethod.GET, path="/endpoint"),
            )
        )

        assert result.success is False
        assert result.error.code.value == "DOWNSTREAM_UNREACHABLE"
        assert "unexpected error" in result.error.message.lower()


class TestEnclaveDispatchBackendEdgeCases:
    """Edge case tests for EnclaveDispatchBackend."""

    @pytest.mark.asyncio
    async def test_enclave_dispatch_unexpected_exception(self, respx_mock):
        """Unexpected exceptions should be caught and logged."""
        import httpx

        from dedalus_mcp.dispatch import (
            EnclaveDispatchBackend,
            DispatchWireRequest,
            HttpMethod,
            HttpRequest,
        )

        respx_mock.post("https://enclave.example.com/dispatch").mock(
            side_effect=RuntimeError("Unexpected error")
        )

        backend = EnclaveDispatchBackend(
            enclave_url="https://enclave.example.com",
            access_token="test_token",
        )

        result = await backend.dispatch(
            DispatchWireRequest(
                connection_handle="ddls:conn:github",
                request=HttpRequest(method=HttpMethod.GET, path="/user"),
            )
        )

        assert result.success is False
        assert result.error.code.value == "DOWNSTREAM_UNREACHABLE"

    def test_sign_request_without_deployment_auth(self):
        """Signing without deployment_id/auth_secret should return empty dict."""
        from dedalus_mcp.dispatch import EnclaveDispatchBackend

        backend = EnclaveDispatchBackend(
            enclave_url="https://enclave.example.com",
            access_token="test_token",
            deployment_id=None,
            auth_secret=None,
        )

        headers = backend._sign_request(b"test body")
        assert headers == {}

    def test_generate_dpop_proof_without_key(self):
        """DPoP proof generation without key should return empty string."""
        from dedalus_mcp.dispatch import EnclaveDispatchBackend

        backend = EnclaveDispatchBackend(
            enclave_url="https://enclave.example.com",
            access_token="test_token",
            dpop_key=None,
        )

        proof = backend._generate_dpop_proof("https://example.com/api", "POST")
        assert proof == ""


class TestCreateDispatchBackendFromEnv:
    """Tests for create_dispatch_backend_from_env factory."""

    def test_creates_enclave_backend_when_url_set(self, monkeypatch):
        """Should create EnclaveDispatchBackend when DEDALUS_DISPATCH_URL is set."""
        import base64

        from dedalus_mcp.dispatch import EnclaveDispatchBackend, create_dispatch_backend_from_env

        monkeypatch.setenv("DEDALUS_DISPATCH_URL", "https://enclave.example.com")
        monkeypatch.setenv("DEDALUS_DEPLOYMENT_ID", "dep_01ABC")
        monkeypatch.setenv("DEDALUS_AUTH_SECRET", base64.b64encode(b"0" * 32).decode())

        backend = create_dispatch_backend_from_env()
        assert isinstance(backend, EnclaveDispatchBackend)

    def test_creates_direct_backend_when_url_not_set(self, monkeypatch):
        """Should create DirectDispatchBackend when DEDALUS_DISPATCH_URL not set."""
        from dedalus_mcp.dispatch import DirectDispatchBackend, create_dispatch_backend_from_env

        monkeypatch.delenv("DEDALUS_DISPATCH_URL", raising=False)

        backend = create_dispatch_backend_from_env()
        assert isinstance(backend, DirectDispatchBackend)


class TestDispatchResponseConformance:
    """Conformance tests for DispatchResponse wire format (ADR-013)."""

    @pytest.mark.asyncio
    async def test_enclave_dispatch_handles_unknown_error_code(self, respx_mock):
        """Unknown error codes should fall back to DOWNSTREAM_UNREACHABLE."""
        import httpx

        from dedalus_mcp.dispatch import (
            EnclaveDispatchBackend,
            DispatchErrorCode,
            DispatchWireRequest,
            HttpMethod,
            HttpRequest,
        )

        # Simulate enclave returning an unknown error code
        respx_mock.post("https://enclave.example.com/dispatch").mock(
            return_value=httpx.Response(
                200,
                json={
                    "success": False,
                    "error": {
                        "code": "SOME_FUTURE_ERROR_CODE",
                        "message": "Some new error",
                        "retryable": False,
                    },
                },
            )
        )

        backend = EnclaveDispatchBackend(
            enclave_url="https://enclave.example.com",
            access_token="test_token",
        )

        result = await backend.dispatch(
            DispatchWireRequest(
                connection_handle="ddls:conn:github",
                request=HttpRequest(method=HttpMethod.GET, path="/user"),
            )
        )

        assert result.success is False
        assert result.error.code == DispatchErrorCode.DOWNSTREAM_UNREACHABLE
        assert result.error.message == "Some new error"

    def test_dispatch_error_code_wire_format(self):
        """Error codes must be SCREAMING_CASE on the wire."""
        from dedalus_mcp.dispatch import DispatchErrorCode

        # All error codes should be uppercase (wire format)
        for code in DispatchErrorCode:
            assert code.value == code.value.upper(), f"{code.name} value must be uppercase"
            assert "_" in code.value or code.value.isalpha(), f"{code.name} must be SCREAMING_CASE"


class TestDispatchIntegration:
    """Integration tests for dispatch flow."""

    @pytest.mark.asyncio
    async def test_dispatch_validates_handle_format(self):
        """Dispatch should validate handle format before forwarding."""
        from dedalus_mcp.server.services.connection_gate import (
            InvalidConnectionHandleError,
            validate_handle_format,
        )

        # Valid handles should pass format check
        validate_handle_format("ddls:conn:github")  # No raise
        validate_handle_format("ddls:conn_env_supabase_key")  # No raise

        # Invalid format should fail before dispatch
        with pytest.raises(InvalidConnectionHandleError):
            validate_handle_format("invalid-handle-format")
