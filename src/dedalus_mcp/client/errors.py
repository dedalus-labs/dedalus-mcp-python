# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Connection error types for MCPClient.

These exceptions provide specific, actionable error messages for HTTP status
codes encountered during MCP connection per the spec:
- RFC 9728 (OAuth Protected Resource Metadata)
- MCP Transport Specification
- MCP Authorization Specification
"""

from __future__ import annotations


class MCPConnectionError(Exception):
    """Base class for MCP connection errors.

    All HTTP status code errors during connection inherit from this class.

    Attributes:
        status_code: HTTP status code that triggered the error.
        message: Human-readable error description.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message

    def __str__(self) -> str:
        if self.status_code:
            return f"[{self.status_code}] {self.message}"
        return self.message


class BadRequestError(MCPConnectionError):
    """400 Bad Request - Invalid input or protocol version.

    Raised when:
    - Invalid MCP-Protocol-Version header
    - Malformed JSON-RPC request
    - Invalid request parameters (422)
    """

    def __init__(
        self,
        message: str = "Bad request to MCP server",
        *,
        status_code: int = 400,
    ) -> None:
        super().__init__(message, status_code=status_code)


class AuthRequiredError(MCPConnectionError):
    """401 Unauthorized - Authentication required or token invalid.

    Raised when:
    - No credentials provided to protected resource
    - Access token expired or invalid
    - Token signature verification failed

    Attributes:
        www_authenticate: The WWW-Authenticate header value, if present.
    """

    def __init__(
        self,
        message: str = "Authentication required",
        *,
        status_code: int = 401,
        www_authenticate: str | None = None,
    ) -> None:
        super().__init__(message, status_code=status_code)
        self.www_authenticate = www_authenticate


class ForbiddenError(MCPConnectionError):
    """403 Forbidden - Insufficient scopes or permissions.

    Raised when:
    - Token lacks required scopes
    - User/client lacks permission for the requested operation
    """

    def __init__(
        self,
        message: str = "Access forbidden - insufficient permissions",
        *,
        status_code: int = 403,
    ) -> None:
        super().__init__(message, status_code=status_code)


class SessionExpiredError(MCPConnectionError):
    """404 Not Found - Session terminated or expired.

    Per MCP Transport spec, 404 during an active session indicates
    the session has been terminated by the server.

    Raised when:
    - Session ID is no longer valid
    - Server terminated the session
    """

    def __init__(
        self,
        message: str = "Session expired or terminated",
        *,
        status_code: int = 404,
    ) -> None:
        super().__init__(message, status_code=status_code)


class TransportError(MCPConnectionError):
    """405/415 - Transport or protocol mismatch.

    Raised when:
    - HTTP method not allowed (405)
    - Wrong Content-Type (415)
    - Transport type incompatibility
    """

    def __init__(
        self,
        message: str = "Transport error - protocol mismatch",
        *,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message, status_code=status_code)


class ServerError(MCPConnectionError):
    """5xx Server Error - Server-side failure.

    Raised when:
    - 500 Internal Server Error
    - 502 Bad Gateway
    - 503 Service Unavailable
    - 504 Gateway Timeout

    Attributes:
        retry_after: The Retry-After header value, if present.
    """

    def __init__(
        self,
        message: str = "Server error",
        *,
        status_code: int = 500,
        retry_after: str | None = None,
    ) -> None:
        super().__init__(message, status_code=status_code)
        self.retry_after = retry_after


__all__ = [
    "MCPConnectionError",
    "BadRequestError",
    "AuthRequiredError",
    "ForbiddenError",
    "SessionExpiredError",
    "TransportError",
    "ServerError",
]
