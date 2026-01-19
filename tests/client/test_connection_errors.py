# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""TDD tests for MCPClient connection error handling.

These tests define the expected behavior for HTTP status codes during
MCP connection per the spec:
- RFC 9728 (OAuth Protected Resource Metadata)
- MCP Transport Specification (2025-11-25)
- MCP Authorization Specification

Each error should produce a specific, actionable error message.
"""

from __future__ import annotations

import pytest
import httpx
import respx


# =============================================================================
# Expected Exception Types (TDD: Define interface first)
# =============================================================================


class TestConnectionErrorTypes:
    """Verify that connection error types exist and have expected hierarchy."""

    def test_mcp_connection_error_exists(self):
        """MCPConnectionError should be the base for all connection errors."""
        from dedalus_mcp.client.errors import MCPConnectionError

        assert issubclass(MCPConnectionError, Exception)

    def test_auth_required_error_exists(self):
        """AuthRequiredError for 401 responses."""
        from dedalus_mcp.client.errors import AuthRequiredError, MCPConnectionError

        assert issubclass(AuthRequiredError, MCPConnectionError)

    def test_forbidden_error_exists(self):
        """ForbiddenError for 403 responses."""
        from dedalus_mcp.client.errors import ForbiddenError, MCPConnectionError

        assert issubclass(ForbiddenError, MCPConnectionError)

    def test_session_expired_error_exists(self):
        """SessionExpiredError for 404 responses (session terminated)."""
        from dedalus_mcp.client.errors import SessionExpiredError, MCPConnectionError

        assert issubclass(SessionExpiredError, MCPConnectionError)

    def test_transport_error_exists(self):
        """TransportError for 405/415 responses (protocol mismatch)."""
        from dedalus_mcp.client.errors import TransportError, MCPConnectionError

        assert issubclass(TransportError, MCPConnectionError)

    def test_bad_request_error_exists(self):
        """BadRequestError for 400 responses."""
        from dedalus_mcp.client.errors import BadRequestError, MCPConnectionError

        assert issubclass(BadRequestError, MCPConnectionError)

    def test_server_error_exists(self):
        """ServerError for 5xx responses."""
        from dedalus_mcp.client.errors import ServerError, MCPConnectionError

        assert issubclass(ServerError, MCPConnectionError)


# =============================================================================
# 400 Bad Request Tests (MCP Transport Spec)
# =============================================================================


class TestBadRequestErrors:
    """Tests for 400 Bad Request handling.

    Per MCP spec, 400 indicates:
    - Invalid input (malformed JSON-RPC)
    - Invalid MCP-Protocol-Version header
    - Malformed authorization request
    """

    @respx.mock
    @pytest.mark.anyio
    async def test_400_invalid_protocol_version(self):
        """400 with version error produces BadRequestError.

        Note: When the response body isn't readable (streaming), we fall back
        to a generic message. The key behavior is raising BadRequestError.
        """
        from dedalus_mcp.client import MCPClient
        from dedalus_mcp.client.errors import BadRequestError

        respx.post("https://mcp.example.com/mcp").mock(
            return_value=httpx.Response(
                400,
                json={"error": "invalid_request", "error_description": "Unsupported MCP-Protocol-Version: 2023-01-01"},
            )
        )

        with pytest.raises(BadRequestError) as exc_info:
            await MCPClient.connect("https://mcp.example.com/mcp")

        # Should be BadRequestError with status code 400
        assert exc_info.value.status_code == 400

    @respx.mock
    @pytest.mark.anyio
    async def test_400_malformed_json_rpc(self):
        """400 with parse error produces actionable BadRequestError."""
        from dedalus_mcp.client import MCPClient
        from dedalus_mcp.client.errors import BadRequestError

        respx.post("https://mcp.example.com/mcp").mock(
            return_value=httpx.Response(
                400, json={"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}, "id": None}
            )
        )

        with pytest.raises(BadRequestError) as exc_info:
            await MCPClient.connect("https://mcp.example.com/mcp")

        assert "400" in str(exc_info.value) or "request" in str(exc_info.value).lower()

    @respx.mock
    @pytest.mark.anyio
    async def test_400_generic_bad_request(self):
        """400 without specific error info still produces BadRequestError."""
        from dedalus_mcp.client import MCPClient
        from dedalus_mcp.client.errors import BadRequestError

        respx.post("https://mcp.example.com/mcp").mock(return_value=httpx.Response(400, text="Bad Request"))

        with pytest.raises(BadRequestError):
            await MCPClient.connect("https://mcp.example.com/mcp")


# =============================================================================
# 401 Unauthorized Tests (MCP Authorization Spec)
# =============================================================================


class TestAuthRequiredErrors:
    """Tests for 401 Unauthorized handling.

    Per MCP Authorization spec, 401 indicates:
    - Authorization required
    - Token invalid or expired
    """

    @respx.mock
    @pytest.mark.anyio
    async def test_401_no_credentials(self):
        """401 without credentials produces AuthRequiredError."""
        from dedalus_mcp.client import MCPClient
        from dedalus_mcp.client.errors import AuthRequiredError

        respx.post("https://mcp.example.com/mcp").mock(
            return_value=httpx.Response(
                401, headers={"WWW-Authenticate": 'Bearer resource_metadata="/.well-known/oauth-protected-resource"'}
            )
        )

        with pytest.raises(AuthRequiredError) as exc_info:
            await MCPClient.connect("https://mcp.example.com/mcp")

        # Should mention auth/credentials
        err = str(exc_info.value).lower()
        assert "auth" in err or "credential" in err or "unauthorized" in err

    @respx.mock
    @pytest.mark.anyio
    async def test_401_invalid_token(self):
        """401 with invalid_token error produces AuthRequiredError."""
        from dedalus_mcp.client import MCPClient
        from dedalus_mcp.client.errors import AuthRequiredError

        respx.post("https://mcp.example.com/mcp").mock(
            return_value=httpx.Response(
                401, headers={"WWW-Authenticate": 'Bearer error="invalid_token", error_description="Token has expired"'}
            )
        )

        with pytest.raises(AuthRequiredError) as exc_info:
            await MCPClient.connect("https://mcp.example.com/mcp")

        # Should mention token expiration or invalidity
        err = str(exc_info.value).lower()
        assert "token" in err or "expired" in err or "invalid" in err

    @respx.mock
    @pytest.mark.anyio
    async def test_401_includes_www_authenticate_info(self):
        """AuthRequiredError should include WWW-Authenticate details when available."""
        from dedalus_mcp.client import MCPClient
        from dedalus_mcp.client.errors import AuthRequiredError

        respx.post("https://mcp.example.com/mcp").mock(
            return_value=httpx.Response(401, headers={"WWW-Authenticate": 'Bearer realm="mcp", error="invalid_token"'})
        )

        with pytest.raises(AuthRequiredError) as exc_info:
            await MCPClient.connect("https://mcp.example.com/mcp")

        # The error should preserve useful auth context
        assert exc_info.value.www_authenticate is not None or "Bearer" in str(exc_info.value)


# =============================================================================
# 403 Forbidden Tests (MCP Authorization Spec)
# =============================================================================


class TestForbiddenErrors:
    """Tests for 403 Forbidden handling.

    Per MCP Authorization spec, 403 indicates:
    - Invalid scopes
    - Insufficient permissions
    """

    @respx.mock
    @pytest.mark.anyio
    async def test_403_insufficient_scope(self):
        """403 with insufficient_scope error produces ForbiddenError."""
        from dedalus_mcp.client import MCPClient
        from dedalus_mcp.client.errors import ForbiddenError

        respx.post("https://mcp.example.com/mcp").mock(
            return_value=httpx.Response(
                403, headers={"WWW-Authenticate": 'Bearer error="insufficient_scope", scope="mcp:admin"'}
            )
        )

        with pytest.raises(ForbiddenError) as exc_info:
            await MCPClient.connect("https://mcp.example.com/mcp")

        # Should mention scope/permission
        err = str(exc_info.value).lower()
        assert "scope" in err or "permission" in err or "forbidden" in err

    @respx.mock
    @pytest.mark.anyio
    async def test_403_generic_forbidden(self):
        """403 without specific error still produces ForbiddenError."""
        from dedalus_mcp.client import MCPClient
        from dedalus_mcp.client.errors import ForbiddenError

        respx.post("https://mcp.example.com/mcp").mock(return_value=httpx.Response(403, text="Forbidden"))

        with pytest.raises(ForbiddenError) as exc_info:
            await MCPClient.connect("https://mcp.example.com/mcp")

        assert "403" in str(exc_info.value) or "forbidden" in str(exc_info.value).lower()


# =============================================================================
# 404 Not Found Tests (MCP Transport Spec)
# =============================================================================


class TestSessionExpiredErrors:
    """Tests for 404 Not Found handling.

    Per MCP Transport spec, 404 during a session indicates:
    - Session has been terminated
    - Session ID is expired or invalid
    """

    @respx.mock
    @pytest.mark.anyio
    async def test_404_session_terminated(self):
        """404 with session context produces SessionExpiredError."""
        from dedalus_mcp.client import MCPClient
        from dedalus_mcp.client.errors import SessionExpiredError

        respx.post("https://mcp.example.com/mcp").mock(
            return_value=httpx.Response(
                404, json={"error": "session_not_found", "message": "Session has been terminated"}
            )
        )

        with pytest.raises(SessionExpiredError) as exc_info:
            await MCPClient.connect("https://mcp.example.com/mcp")

        # Should mention session
        err = str(exc_info.value).lower()
        assert "session" in err or "terminated" in err or "expired" in err

    @respx.mock
    @pytest.mark.anyio
    async def test_404_endpoint_not_found(self):
        """404 for endpoint not found produces MCPConnectionError."""
        from dedalus_mcp.client import MCPClient
        from dedalus_mcp.client.errors import MCPConnectionError

        respx.post("https://mcp.example.com/mcp").mock(return_value=httpx.Response(404, text="Not Found"))

        with pytest.raises(MCPConnectionError) as exc_info:
            await MCPClient.connect("https://mcp.example.com/mcp")

        # Should provide helpful message about endpoint
        err = str(exc_info.value).lower()
        assert "404" in str(exc_info.value) or "not found" in err or "endpoint" in err


# =============================================================================
# 405 Method Not Allowed Tests (MCP Transport Spec)
# =============================================================================


class TestMethodNotAllowedErrors:
    """Tests for 405 Method Not Allowed handling.

    Per MCP Transport spec, 405 indicates:
    - Server doesn't support GET (for SSE)
    - Wrong HTTP method for the endpoint
    """

    @respx.mock
    @pytest.mark.anyio
    async def test_405_method_not_allowed(self):
        """405 produces TransportError with method suggestion."""
        from dedalus_mcp.client import MCPClient
        from dedalus_mcp.client.errors import TransportError

        respx.post("https://mcp.example.com/mcp").mock(
            return_value=httpx.Response(405, headers={"Allow": "GET"}, text="Method Not Allowed")
        )

        with pytest.raises(TransportError) as exc_info:
            await MCPClient.connect("https://mcp.example.com/mcp")

        # Should mention method/transport
        err = str(exc_info.value).lower()
        assert "method" in err or "405" in str(exc_info.value) or "transport" in err


# =============================================================================
# 415 Unsupported Media Type Tests
# =============================================================================


class TestUnsupportedMediaTypeErrors:
    """Tests for 415 Unsupported Media Type handling.

    415 indicates wrong Content-Type header for the request.
    """

    @respx.mock
    @pytest.mark.anyio
    async def test_415_wrong_content_type(self):
        """415 produces TransportError with content-type info."""
        from dedalus_mcp.client import MCPClient
        from dedalus_mcp.client.errors import TransportError

        respx.post("https://mcp.example.com/mcp").mock(
            return_value=httpx.Response(415, json={"error": "Expected application/json"})
        )

        with pytest.raises(TransportError) as exc_info:
            await MCPClient.connect("https://mcp.example.com/mcp")

        # Should mention content-type or media type
        err = str(exc_info.value).lower()
        assert "content" in err or "media" in err or "415" in str(exc_info.value)


# =============================================================================
# 422 Unprocessable Entity Tests
# =============================================================================


class TestUnprocessableEntityErrors:
    """Tests for 422 Unprocessable Entity handling.

    422 indicates semantic errors in the request:
    - Invalid JSON-RPC structure
    - Missing required fields
    """

    @respx.mock
    @pytest.mark.anyio
    async def test_422_invalid_jsonrpc(self):
        """422 produces BadRequestError with validation info."""
        from dedalus_mcp.client import MCPClient
        from dedalus_mcp.client.errors import BadRequestError

        respx.post("https://mcp.example.com/mcp").mock(
            return_value=httpx.Response(
                422, json={"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}, "id": None}
            )
        )

        with pytest.raises(BadRequestError) as exc_info:
            await MCPClient.connect("https://mcp.example.com/mcp")

        err = str(exc_info.value).lower()
        assert "invalid" in err or "422" in str(exc_info.value) or "request" in err


# =============================================================================
# 5xx Server Error Tests
# =============================================================================


class TestServerErrors:
    """Tests for 5xx server error handling."""

    @respx.mock
    @pytest.mark.anyio
    async def test_500_internal_server_error(self):
        """500 produces ServerError."""
        from dedalus_mcp.client import MCPClient
        from dedalus_mcp.client.errors import ServerError

        respx.post("https://mcp.example.com/mcp").mock(return_value=httpx.Response(500, text="Internal Server Error"))

        with pytest.raises(ServerError) as exc_info:
            await MCPClient.connect("https://mcp.example.com/mcp")

        err = str(exc_info.value).lower()
        assert "server" in err or "500" in str(exc_info.value)

    @respx.mock
    @pytest.mark.anyio
    async def test_502_bad_gateway(self):
        """502 produces ServerError with gateway context."""
        from dedalus_mcp.client import MCPClient
        from dedalus_mcp.client.errors import ServerError

        respx.post("https://mcp.example.com/mcp").mock(return_value=httpx.Response(502, text="Bad Gateway"))

        with pytest.raises(ServerError) as exc_info:
            await MCPClient.connect("https://mcp.example.com/mcp")

        err = str(exc_info.value).lower()
        assert "gateway" in err or "502" in str(exc_info.value) or "server" in err

    @respx.mock
    @pytest.mark.anyio
    async def test_503_service_unavailable(self):
        """503 produces ServerError suggesting retry."""
        from dedalus_mcp.client import MCPClient
        from dedalus_mcp.client.errors import ServerError

        respx.post("https://mcp.example.com/mcp").mock(
            return_value=httpx.Response(503, headers={"Retry-After": "30"}, text="Service Unavailable")
        )

        with pytest.raises(ServerError) as exc_info:
            await MCPClient.connect("https://mcp.example.com/mcp")

        # Should mention unavailable or retry
        err = str(exc_info.value).lower()
        assert "unavailable" in err or "503" in str(exc_info.value) or "retry" in err

    @respx.mock
    @pytest.mark.anyio
    async def test_504_gateway_timeout(self):
        """504 produces ServerError with timeout context."""
        from dedalus_mcp.client import MCPClient
        from dedalus_mcp.client.errors import ServerError

        respx.post("https://mcp.example.com/mcp").mock(return_value=httpx.Response(504, text="Gateway Timeout"))

        with pytest.raises(ServerError) as exc_info:
            await MCPClient.connect("https://mcp.example.com/mcp")

        err = str(exc_info.value).lower()
        assert "timeout" in err or "504" in str(exc_info.value) or "gateway" in err


# =============================================================================
# Error Attribute Tests
# =============================================================================


class TestErrorAttributes:
    """Tests for error objects having useful attributes."""

    @respx.mock
    @pytest.mark.anyio
    async def test_connection_error_has_status_code(self):
        """MCPConnectionError should expose the HTTP status code."""
        from dedalus_mcp.client import MCPClient
        from dedalus_mcp.client.errors import MCPConnectionError

        respx.post("https://mcp.example.com/mcp").mock(return_value=httpx.Response(418, text="I'm a teapot"))

        with pytest.raises(MCPConnectionError) as exc_info:
            await MCPClient.connect("https://mcp.example.com/mcp")

        assert exc_info.value.status_code == 418

    @respx.mock
    @pytest.mark.anyio
    async def test_auth_error_has_www_authenticate(self):
        """AuthRequiredError should expose WWW-Authenticate header."""
        from dedalus_mcp.client import MCPClient
        from dedalus_mcp.client.errors import AuthRequiredError

        respx.post("https://mcp.example.com/mcp").mock(
            return_value=httpx.Response(401, headers={"WWW-Authenticate": 'Bearer realm="mcp"'})
        )

        with pytest.raises(AuthRequiredError) as exc_info:
            await MCPClient.connect("https://mcp.example.com/mcp")

        assert exc_info.value.www_authenticate == 'Bearer realm="mcp"'

    @respx.mock
    @pytest.mark.anyio
    async def test_server_error_has_retry_after(self):
        """ServerError should expose Retry-After header when present."""
        from dedalus_mcp.client import MCPClient
        from dedalus_mcp.client.errors import ServerError

        respx.post("https://mcp.example.com/mcp").mock(
            return_value=httpx.Response(503, headers={"Retry-After": "60"}, text="Service Unavailable")
        )

        with pytest.raises(ServerError) as exc_info:
            await MCPClient.connect("https://mcp.example.com/mcp")

        assert exc_info.value.retry_after == "60"


# =============================================================================
# Network-Level Error Tests
# =============================================================================


class TestNetworkErrors:
    """Tests for network-level failures (not HTTP status codes)."""

    @respx.mock
    @pytest.mark.anyio
    async def test_connection_refused(self):
        """Connection refused produces MCPConnectionError."""
        from dedalus_mcp.client import MCPClient
        from dedalus_mcp.client.errors import MCPConnectionError

        respx.post("https://mcp.example.com/mcp").mock(side_effect=httpx.ConnectError("Connection refused"))

        with pytest.raises(MCPConnectionError) as exc_info:
            await MCPClient.connect("https://mcp.example.com/mcp")

        err = str(exc_info.value).lower()
        assert "connect" in err or "refused" in err

    @respx.mock
    @pytest.mark.anyio
    async def test_dns_resolution_failure(self):
        """DNS failure produces MCPConnectionError."""
        from dedalus_mcp.client import MCPClient
        from dedalus_mcp.client.errors import MCPConnectionError

        respx.post("https://nonexistent.invalid/mcp").mock(side_effect=httpx.ConnectError("Name or service not known"))

        with pytest.raises(MCPConnectionError) as exc_info:
            await MCPClient.connect("https://nonexistent.invalid/mcp")

        err = str(exc_info.value).lower()
        assert "connect" in err or "dns" in err or "resolve" in err

    @respx.mock
    @pytest.mark.anyio
    async def test_timeout(self):
        """Request timeout produces MCPConnectionError."""
        from dedalus_mcp.client import MCPClient
        from dedalus_mcp.client.errors import MCPConnectionError

        respx.post("https://mcp.example.com/mcp").mock(side_effect=httpx.TimeoutException("Request timed out"))

        with pytest.raises(MCPConnectionError) as exc_info:
            await MCPClient.connect("https://mcp.example.com/mcp")

        err = str(exc_info.value).lower()
        assert "timeout" in err or "timed out" in err
