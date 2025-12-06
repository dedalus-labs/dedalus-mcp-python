# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Tests for HTTP-based dispatch model.

This tests the new dispatch interface where:
- MCP servers define Connection objects
- ctx.dispatch() accepts HttpRequest
- Wire format is {connection_handle, request: HttpRequest}
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError


# =============================================================================
# HttpMethod Tests
# =============================================================================


class TestHttpMethod:
    """Tests for HttpMethod enum."""

    def test_http_methods_exist(self):
        """HttpMethod should define standard HTTP methods."""
        from dedalus_mcp.dispatch import HttpMethod

        assert HttpMethod.GET == "GET"
        assert HttpMethod.POST == "POST"
        assert HttpMethod.PUT == "PUT"
        assert HttpMethod.PATCH == "PATCH"
        assert HttpMethod.DELETE == "DELETE"

    def test_http_method_is_string_enum(self):
        """HttpMethod should be usable as string."""
        from dedalus_mcp.dispatch import HttpMethod

        assert f"{HttpMethod.GET}" == "GET"
        assert HttpMethod.POST.value == "POST"


# =============================================================================
# HttpRequest Tests
# =============================================================================


class TestHttpRequest:
    """Tests for HttpRequest model."""

    def test_minimal_request(self):
        """HttpRequest requires method and path."""
        from dedalus_mcp.dispatch import HttpMethod, HttpRequest

        req = HttpRequest(method=HttpMethod.GET, path="/user")

        assert req.method == HttpMethod.GET
        assert req.path == "/user"
        assert req.body is None
        assert req.headers is None
        assert req.timeout_ms is None

    def test_full_request(self):
        """HttpRequest with all fields."""
        from dedalus_mcp.dispatch import HttpMethod, HttpRequest

        req = HttpRequest(
            method=HttpMethod.POST,
            path="/repos/owner/repo/issues",
            body={"title": "Bug", "body": "Description"},
            headers={"Accept": "application/json"},
            timeout_ms=5000,
        )

        assert req.method == HttpMethod.POST
        assert req.path == "/repos/owner/repo/issues"
        assert req.body == {"title": "Bug", "body": "Description"}
        assert req.headers == {"Accept": "application/json"}
        assert req.timeout_ms == 5000

    def test_path_must_start_with_slash(self):
        """Path must start with /."""
        from dedalus_mcp.dispatch import HttpMethod, HttpRequest

        with pytest.raises(ValidationError) as exc:
            HttpRequest(method=HttpMethod.GET, path="user")

        assert "path" in str(exc.value).lower()

    def test_path_with_query_string(self):
        """Path can include query string."""
        from dedalus_mcp.dispatch import HttpMethod, HttpRequest

        req = HttpRequest(method=HttpMethod.GET, path="/search?q=foo&limit=10")

        assert req.path == "/search?q=foo&limit=10"

    def test_authorization_header_forbidden(self):
        """Cannot override Authorization header."""
        from dedalus_mcp.dispatch import HttpMethod, HttpRequest

        with pytest.raises(ValidationError) as exc:
            HttpRequest(
                method=HttpMethod.GET,
                path="/user",
                headers={"Authorization": "Bearer malicious"},
            )

        assert "authorization" in str(exc.value).lower()

    def test_dpop_header_forbidden(self):
        """Cannot set DPoP header."""
        from dedalus_mcp.dispatch import HttpMethod, HttpRequest

        with pytest.raises(ValidationError):
            HttpRequest(
                method=HttpMethod.GET,
                path="/user",
                headers={"DPoP": "malicious-proof"},
            )

    def test_timeout_bounds(self):
        """Timeout must be between 1000 and 300000 ms."""
        from dedalus_mcp.dispatch import HttpMethod, HttpRequest

        # Too low
        with pytest.raises(ValidationError):
            HttpRequest(method=HttpMethod.GET, path="/user", timeout_ms=500)

        # Too high
        with pytest.raises(ValidationError):
            HttpRequest(method=HttpMethod.GET, path="/user", timeout_ms=400_000)

        # Valid
        req = HttpRequest(method=HttpMethod.GET, path="/user", timeout_ms=60_000)
        assert req.timeout_ms == 60_000

    def test_body_types(self):
        """Body can be dict, list, or string."""
        from dedalus_mcp.dispatch import HttpMethod, HttpRequest

        # Dict body
        req1 = HttpRequest(method=HttpMethod.POST, path="/data", body={"key": "value"})
        assert req1.body == {"key": "value"}

        # List body
        req2 = HttpRequest(method=HttpMethod.POST, path="/batch", body=[1, 2, 3])
        assert req2.body == [1, 2, 3]

        # String body
        req3 = HttpRequest(method=HttpMethod.POST, path="/raw", body="raw content")
        assert req3.body == "raw content"


# =============================================================================
# HttpResponse Tests
# =============================================================================


class TestHttpResponse:
    """Tests for HttpResponse model."""

    def test_success_response(self):
        """HttpResponse with 200 status."""
        from dedalus_mcp.dispatch import HttpResponse

        resp = HttpResponse(
            status=200,
            headers={"Content-Type": "application/json"},
            body={"id": 123, "name": "test"},
        )

        assert resp.status == 200
        assert resp.headers["Content-Type"] == "application/json"
        assert resp.body == {"id": 123, "name": "test"}

    def test_error_response(self):
        """HttpResponse with 4xx/5xx status."""
        from dedalus_mcp.dispatch import HttpResponse

        resp = HttpResponse(
            status=404,
            headers={},
            body={"error": "Not found"},
        )

        assert resp.status == 404

    def test_status_bounds(self):
        """Status must be valid HTTP status code."""
        from dedalus_mcp.dispatch import HttpResponse

        # Valid range
        HttpResponse(status=100, headers={})
        HttpResponse(status=599, headers={})

        # Invalid
        with pytest.raises(ValidationError):
            HttpResponse(status=99, headers={})

        with pytest.raises(ValidationError):
            HttpResponse(status=600, headers={})


# =============================================================================
# DispatchError Tests
# =============================================================================


class TestDispatchError:
    """Tests for DispatchError and DispatchErrorCode."""

    def test_error_codes_exist(self):
        """DispatchErrorCode should define infrastructure errors."""
        from dedalus_mcp.dispatch import DispatchErrorCode

        assert DispatchErrorCode.CONNECTION_NOT_FOUND == "connection_not_found"
        assert DispatchErrorCode.CONNECTION_REVOKED == "connection_revoked"
        assert DispatchErrorCode.DOWNSTREAM_TIMEOUT == "downstream_timeout"
        assert DispatchErrorCode.DOWNSTREAM_UNREACHABLE == "downstream_unreachable"

    def test_dispatch_error_construction(self):
        """DispatchError should hold code, message, retryable."""
        from dedalus_mcp.dispatch import DispatchError, DispatchErrorCode

        err = DispatchError(
            code=DispatchErrorCode.DOWNSTREAM_TIMEOUT,
            message="Request timed out after 30s",
            retryable=True,
        )

        assert err.code == DispatchErrorCode.DOWNSTREAM_TIMEOUT
        assert err.message == "Request timed out after 30s"
        assert err.retryable is True


# =============================================================================
# DispatchResponse Tests
# =============================================================================


class TestDispatchResponse:
    """Tests for DispatchResponse model."""

    def test_success_response(self):
        """DispatchResponse.ok() factory."""
        from dedalus_mcp.dispatch import DispatchResponse, HttpResponse

        http_resp = HttpResponse(status=200, headers={}, body={"created": True})
        resp = DispatchResponse.ok(http_resp)

        assert resp.success is True
        assert resp.response is not None
        assert resp.response.status == 200
        assert resp.error is None

    def test_error_response(self):
        """DispatchResponse.fail() factory."""
        from dedalus_mcp.dispatch import DispatchErrorCode, DispatchResponse

        resp = DispatchResponse.fail(
            DispatchErrorCode.DOWNSTREAM_TIMEOUT,
            "Timed out",
            retryable=True,
        )

        assert resp.success is False
        assert resp.response is None
        assert resp.error is not None
        assert resp.error.code == DispatchErrorCode.DOWNSTREAM_TIMEOUT
        assert resp.error.retryable is True

    def test_http_4xx_is_success(self):
        """HTTP 4xx/5xx from downstream is success=True (we got a response)."""
        from dedalus_mcp.dispatch import DispatchResponse, HttpResponse

        # 404 from downstream is still "success" - we reached the API
        http_resp = HttpResponse(status=404, headers={}, body={"error": "Not found"})
        resp = DispatchResponse.ok(http_resp)

        assert resp.success is True
        assert resp.response.status == 404


# =============================================================================
# DispatchWireRequest Tests
# =============================================================================


class TestDispatchWireRequest:
    """Tests for wire format sent to gateway/enclave."""

    def test_wire_request_construction(self):
        """DispatchWireRequest holds handle and HttpRequest."""
        from dedalus_mcp.dispatch import DispatchWireRequest, HttpMethod, HttpRequest

        req = HttpRequest(method=HttpMethod.POST, path="/issues", body={"title": "Bug"})
        wire = DispatchWireRequest(connection_handle="ddls:conn:abc123", request=req)

        assert wire.connection_handle == "ddls:conn:abc123"
        assert wire.request.method == HttpMethod.POST
        assert wire.request.path == "/issues"

    def test_wire_request_handle_validation(self):
        """Handle must start with ddls:conn."""
        from dedalus_mcp.dispatch import DispatchWireRequest, HttpMethod, HttpRequest

        req = HttpRequest(method=HttpMethod.GET, path="/user")

        with pytest.raises(ValidationError):
            DispatchWireRequest(connection_handle="invalid:handle", request=req)

        # Valid
        wire = DispatchWireRequest(connection_handle="ddls:conn_env_github", request=req)
        assert wire.connection_handle == "ddls:conn_env_github"
