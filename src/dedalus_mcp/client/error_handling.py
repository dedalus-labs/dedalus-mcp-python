# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Error extraction and conversion utilities for MCPClient.

This module handles the conversion of low-level transport errors (httpx, anyio)
into user-friendly MCPConnectionError subclasses with actionable messages.
"""

from __future__ import annotations

import httpx

from .errors import (
    MCPConnectionError,
    AuthRequiredError,
    BadRequestError,
    ForbiddenError,
    ServerError,
    SessionExpiredError,
    TransportError,
)


def extract_http_error(exc: BaseException) -> httpx.HTTPStatusError | None:
    """Extract HTTPStatusError from an exception or exception group.

    The MCP SDK transport layer raises errors wrapped in ExceptionGroup from anyio.
    This helper extracts the underlying HTTPStatusError if present.
    """
    if isinstance(exc, httpx.HTTPStatusError):
        return exc

    if isinstance(exc, BaseExceptionGroup):
        for sub_exc in exc.exceptions:
            result = extract_http_error(sub_exc)
            if result is not None:
                return result

    return None


def extract_network_error(exc: BaseException) -> httpx.ConnectError | httpx.TimeoutException | None:
    """Extract ConnectError or TimeoutException from an exception group."""
    if isinstance(exc, (httpx.ConnectError, httpx.TimeoutException)):
        return exc

    if isinstance(exc, BaseExceptionGroup):
        for sub_exc in exc.exceptions:
            result = extract_network_error(sub_exc)
            if result is not None:
                return result

    return None


def http_error_to_mcp_error(error: httpx.HTTPStatusError) -> MCPConnectionError:
    """Convert an HTTPStatusError to the appropriate MCPConnectionError subclass."""
    status = error.response.status_code
    headers = error.response.headers

    error_msg = _extract_error_message(error)
    www_auth = headers.get("WWW-Authenticate", "")

    if status == 400:
        return _handle_400(error_msg)
    elif status == 401:
        return _handle_401(error_msg, www_auth)
    elif status == 403:
        return _handle_403(error_msg, www_auth)
    elif status == 404:
        return _handle_404(error_msg)
    elif status == 405:
        return _handle_405(headers)
    elif status == 415:
        return _handle_415(error_msg)
    elif status == 422:
        return _handle_422(error_msg)
    elif 500 <= status < 600:
        return _handle_5xx(status, error_msg, headers)

    # Fallback for other status codes
    msg = f"HTTP error {status}: {error_msg}" if error_msg else f"HTTP error {status}"
    return MCPConnectionError(msg, status_code=status)


def network_error_to_mcp_error(error: Exception) -> MCPConnectionError:
    """Convert network-level errors to MCPConnectionError."""
    err_str = str(error).lower()

    if isinstance(error, httpx.TimeoutException):
        return MCPConnectionError(f"Connection timed out: {error}")

    if isinstance(error, httpx.ConnectError):
        if "refused" in err_str:
            return MCPConnectionError(f"Connection refused - server may be down: {error}")
        if "dns" in err_str or "resolve" in err_str or "name" in err_str:
            return MCPConnectionError(f"DNS resolution failed - check the server URL: {error}")
        return MCPConnectionError(f"Failed to connect: {error}")

    return MCPConnectionError(f"Connection error: {error}")


# ---------------------------------------------------------------------------
# Internal helpers for specific status codes
# ---------------------------------------------------------------------------


def _extract_error_message(error: httpx.HTTPStatusError) -> str:
    """Extract error message from response body, handling streaming responses."""
    try:
        body = error.response.json()
        return body.get("error_description") or body.get("message") or body.get("error", "")
    except httpx.ResponseNotRead:
        return ""
    except Exception:
        try:
            return error.response.text[:200] if error.response.text else ""
        except httpx.ResponseNotRead:
            return ""


def _handle_400(error_msg: str) -> BadRequestError:
    msg = f"Bad request: {error_msg}" if error_msg else "Bad request to MCP server"
    if "version" in error_msg.lower() or "protocol" in error_msg.lower():
        msg = f"Invalid protocol version: {error_msg}"
    return BadRequestError(msg, status_code=400)


def _handle_401(error_msg: str, www_auth: str) -> AuthRequiredError:
    if "invalid_token" in www_auth.lower() or "expired" in error_msg.lower():
        msg = f"Token invalid or expired: {error_msg}" if error_msg else "Token invalid or expired"
    else:
        msg = "Authentication required - provide valid credentials"
    return AuthRequiredError(msg, status_code=401, www_authenticate=www_auth or None)


def _handle_403(error_msg: str, www_auth: str) -> ForbiddenError:
    if "scope" in www_auth.lower() or "scope" in error_msg.lower():
        msg = f"Insufficient scope or permissions: {error_msg}" if error_msg else "Insufficient scope"
    else:
        msg = f"Forbidden: {error_msg}" if error_msg else "Access forbidden - insufficient permissions"
    return ForbiddenError(msg, status_code=403)


def _handle_404(error_msg: str) -> MCPConnectionError:
    if "session" in error_msg.lower():
        return SessionExpiredError(f"Session expired or terminated: {error_msg}", status_code=404)
    msg = f"Endpoint not found (404): {error_msg}" if error_msg else "MCP endpoint not found"
    return MCPConnectionError(msg, status_code=404)


def _handle_405(headers: httpx.Headers) -> TransportError:
    allow = headers.get("Allow", "")
    msg = f"Method not allowed (405). Server accepts: {allow}" if allow else "HTTP method not allowed (405)"
    return TransportError(msg, status_code=405)


def _handle_415(error_msg: str) -> TransportError:
    msg = f"Unsupported content type (415): {error_msg}" if error_msg else "Unsupported media type"
    return TransportError(msg, status_code=415)


def _handle_422(error_msg: str) -> BadRequestError:
    msg = f"Invalid request format (422): {error_msg}" if error_msg else "Unprocessable request"
    return BadRequestError(msg, status_code=422)


def _handle_5xx(status: int, error_msg: str, headers: httpx.Headers) -> ServerError:
    retry_after = headers.get("Retry-After")
    status_messages = {
        500: "Internal server error",
        502: "Bad gateway - upstream server error",
        503: "Service unavailable",
        504: "Gateway timeout - server did not respond in time",
    }
    base_msg = status_messages.get(status, f"Server error ({status})")
    msg = f"{base_msg}: {error_msg}" if error_msg else base_msg
    return ServerError(msg, status_code=status, retry_after=retry_after)


__all__ = [
    "extract_http_error",
    "extract_network_error",
    "http_error_to_mcp_error",
    "network_error_to_mcp_error",
]
