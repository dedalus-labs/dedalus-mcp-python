# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Tests for ToolError exception."""

from __future__ import annotations

import pytest

from dedalus_mcp.exceptions import ToolError


def test_tool_error_basic():
    """ToolError stores message and defaults code to ERROR."""
    err = ToolError("something went wrong")
    assert str(err) == "something went wrong"
    assert err.code == "ERROR"


def test_tool_error_with_code():
    """ToolError accepts custom error codes."""
    err = ToolError("not found", code="NOT_FOUND")
    assert str(err) == "not found"
    assert err.code == "NOT_FOUND"


def test_tool_error_is_exception():
    """ToolError can be raised and caught."""
    try:
        raise ToolError("validation failed", code="VALIDATION_ERROR")
    except ToolError as e:
        assert e.code == "VALIDATION_ERROR"
        assert "validation failed" in str(e)
    else:
        pytest.fail("ToolError was not raised")


def test_tool_error_common_codes():
    """Common error codes work as expected."""
    codes = ["NOT_FOUND", "UNAUTHORIZED", "RATE_LIMITED", "INVALID_INPUT", "INTERNAL"]
    for code in codes:
        err = ToolError(f"error with {code}", code=code)
        assert err.code == code
