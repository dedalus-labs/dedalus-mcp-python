# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Exceptions for MCP tool implementations."""

from __future__ import annotations

from enum import Enum


class ToolErrorCode(str, Enum):
    """Error codes for tool failures, optimized for LLM pattern-matching.

    Framework-level codes (enforced by dedalus_mcp):
        CONNECTION_*, RATE_LIMITED, UNAUTHORIZED, FORBIDDEN, TIMEOUT

    Application-level codes (for tool authors):
        NOT_FOUND, INVALID_INPUT, CONFLICT, INTERNAL, ERROR

    """

    # Connection resolution
    NO_CONNECTIONS = "NO_CONNECTIONS"
    CONNECTION_NOT_FOUND = "CONNECTION_NOT_FOUND"
    CONNECTION_AMBIGUOUS = "CONNECTION_AMBIGUOUS"

    # Rate limiting (MCP spec: "servers MUST rate limit")
    RATE_LIMITED = "RATE_LIMITED"

    # Authorization (MCP spec: "servers MUST implement access controls")
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"

    # Timeouts
    TIMEOUT = "TIMEOUT"

    # Application-level (common patterns for tool authors)
    NOT_FOUND = "NOT_FOUND"
    INVALID_INPUT = "INVALID_INPUT"
    CONFLICT = "CONFLICT"
    INTERNAL = "INTERNAL"
    ERROR = "ERROR"


class ToolError(Exception):
    """Exception for tool failures with structured error codes.

    Use this to return meaningful error information to LLM clients:

        from dedalus_mcp import tool
        from dedalus_mcp.exceptions import ToolError

        @tool(description="Fetch user by ID")
        async def get_user(user_id: str) -> dict:
            user = await db.find_user(user_id)
            if user is None:
                raise ToolError("User not found", code="NOT_FOUND")
            return user

    Common codes (see ToolErrorCode enum):
        - NOT_FOUND: Resource doesn't exist
        - UNAUTHORIZED: Missing or invalid credentials
        - INVALID_INPUT: Bad arguments
        - RATE_LIMITED: Too many requests
        - INTERNAL: Server-side failure
        - CONNECTION_NOT_FOUND: Named connection not in JWT
        - CONNECTION_AMBIGUOUS: Multiple connections, no target specified
        - NO_CONNECTIONS: Server has no connections configured
    """

    def __init__(self, message: str, *, code: str = "ERROR") -> None:
        super().__init__(message)
        self.code = code


class ConnectionResolutionError(ToolError):
    """Error during connection resolution in dispatch.

    Subclass of ToolError so it's automatically caught and returned to LLMs
    with structured error codes.

    Attributes:
        available: List of available connection names (for diagnostics)
        requested: The connection name that was requested (if any)
    """

    def __init__(
        self,
        message: str,
        *,
        code: str,
        available: list[str] | None = None,
        requested: str | None = None,
    ) -> None:
        super().__init__(message, code=code)
        self.available = available or []
        self.requested = requested


__all__ = ["ToolError", "ToolErrorCode", "ConnectionResolutionError"]
