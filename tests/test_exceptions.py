# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Tests for ToolError exception and error code taxonomy."""

from __future__ import annotations

import pytest

from dedalus_mcp.exceptions import ConnectionResolutionError, ToolError, ToolErrorCode


class TestToolErrorBasic:
    """Basic ToolError functionality."""

    def test_defaults_to_error_code(self):
        err = ToolError("something went wrong")
        assert str(err) == "something went wrong"
        assert err.code == "ERROR"

    def test_accepts_string_code(self):
        err = ToolError("not found", code="NOT_FOUND")
        assert err.code == "NOT_FOUND"

    def test_accepts_enum_code(self):
        err = ToolError("rate limited", code=ToolErrorCode.RATE_LIMITED)
        assert err.code == ToolErrorCode.RATE_LIMITED

    def test_can_be_raised(self):
        with pytest.raises(ToolError) as exc_info:
            raise ToolError("validation failed", code="INVALID_INPUT")
        assert exc_info.value.code == "INVALID_INPUT"


class TestToolErrorCodeEnum:
    """ToolErrorCode enum coverage."""

    def test_framework_level_connection_codes(self):
        assert ToolErrorCode.NO_CONNECTIONS == "NO_CONNECTIONS"
        assert ToolErrorCode.CONNECTION_NOT_FOUND == "CONNECTION_NOT_FOUND"
        assert ToolErrorCode.CONNECTION_AMBIGUOUS == "CONNECTION_AMBIGUOUS"

    def test_framework_level_rate_limiting(self):
        assert ToolErrorCode.RATE_LIMITED == "RATE_LIMITED"

    def test_framework_level_auth_codes(self):
        assert ToolErrorCode.UNAUTHORIZED == "UNAUTHORIZED"
        assert ToolErrorCode.FORBIDDEN == "FORBIDDEN"

    def test_framework_level_timeout(self):
        assert ToolErrorCode.TIMEOUT == "TIMEOUT"

    def test_application_level_codes(self):
        assert ToolErrorCode.NOT_FOUND == "NOT_FOUND"
        assert ToolErrorCode.INVALID_INPUT == "INVALID_INPUT"
        assert ToolErrorCode.CONFLICT == "CONFLICT"
        assert ToolErrorCode.INTERNAL == "INTERNAL"
        assert ToolErrorCode.ERROR == "ERROR"

    def test_all_codes_are_screaming_case(self):
        for code in ToolErrorCode:
            assert code.value == code.value.upper()


class TestConnectionResolutionError:
    """ConnectionResolutionError for dispatch failures."""

    def test_inherits_from_tool_error(self):
        err = ConnectionResolutionError("msg", code="CONNECTION_NOT_FOUND")
        assert isinstance(err, ToolError)

    def test_includes_diagnostics(self):
        err = ConnectionResolutionError(
            "Connection 'gmail' not found",
            code="CONNECTION_NOT_FOUND",
            available=["github", "slack"],
            requested="gmail",
        )
        assert err.available == ["github", "slack"]
        assert err.requested == "gmail"

    def test_connection_not_found(self):
        err = ConnectionResolutionError(
            "Connection 'gmail' not found. Available: ['gmail-mcp']",
            code="CONNECTION_NOT_FOUND",
            available=["gmail-mcp"],
            requested="gmail",
        )
        assert "gmail-mcp" in err.available

    def test_connection_ambiguous(self):
        err = ConnectionResolutionError(
            "Multiple connections configured; specify target",
            code="CONNECTION_AMBIGUOUS",
            available=["github", "slack", "gmail"],
        )
        assert len(err.available) == 3

    def test_no_connections(self):
        err = ConnectionResolutionError(
            "No connections configured",
            code="NO_CONNECTIONS",
            available=[],
        )
        assert err.available == []


class TestErrorMessageFormat:
    """Error formatting for LLM consumption."""

    def test_code_prefix_format(self):
        err = ToolError("User not found", code="NOT_FOUND")
        formatted = f"[{err.code}] {err}"
        assert formatted == "[NOT_FOUND] User not found"

    def test_connection_error_is_actionable(self):
        """LLM should be able to infer the correction from the error."""
        err = ConnectionResolutionError(
            "Connection 'gmail' not found. Available: ['gmail-mcp']",
            code="CONNECTION_NOT_FOUND",
            available=["gmail-mcp"],
            requested="gmail",
        )
        assert "gmail-mcp" in str(err)


class TestErrorCodeUsagePatterns:
    """Document usage patterns via tests."""

    def test_rate_limited(self):
        err = ToolError(
            "Rate limit exceeded. Retry after 60 seconds.",
            code=ToolErrorCode.RATE_LIMITED,
        )
        assert "Retry" in str(err)

    def test_unauthorized_vs_forbidden(self):
        # 401: no/invalid creds
        unauth = ToolError("No API key provided", code=ToolErrorCode.UNAUTHORIZED)
        assert unauth.code == "UNAUTHORIZED"

        # 403: creds ok but no permission
        forbidden = ToolError(
            "API key valid but lacks 'write' scope",
            code=ToolErrorCode.FORBIDDEN,
        )
        assert forbidden.code == "FORBIDDEN"

    def test_not_found(self):
        err = ToolError("User with ID 'abc123' not found", code=ToolErrorCode.NOT_FOUND)
        assert err.code == "NOT_FOUND"

    def test_invalid_input(self):
        err = ToolError(
            "Date must be in the future. Current date is 2026-01-25.",
            code=ToolErrorCode.INVALID_INPUT,
        )
        assert err.code == "INVALID_INPUT"

    def test_conflict(self):
        err = ToolError(
            "User with email 'test@example.com' already exists",
            code=ToolErrorCode.CONFLICT,
        )
        assert err.code == "CONFLICT"
