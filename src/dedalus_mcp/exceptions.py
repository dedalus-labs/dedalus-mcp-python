# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Exceptions for MCP tool implementations."""

from __future__ import annotations


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

    Common codes:
        - NOT_FOUND: Resource doesn't exist
        - UNAUTHORIZED: Missing or invalid credentials
        - INVALID_INPUT: Bad arguments
        - RATE_LIMITED: Too many requests
        - INTERNAL: Server-side failure
    """

    def __init__(self, message: str, *, code: str = "ERROR") -> None:
        super().__init__(message)
        self.code = code


__all__ = ["ToolError"]
