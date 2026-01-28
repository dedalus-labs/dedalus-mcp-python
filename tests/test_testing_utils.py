# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Tests for testing utilities (mock_context)."""

from __future__ import annotations

import pytest

from dedalus_mcp import get_context, tool
from dedalus_mcp.testing import mock_context


def test_mock_context_provides_context():
    """mock_context makes get_context() work outside request handlers."""
    with mock_context() as ctx:
        assert get_context() is ctx


def test_mock_context_cleans_up():
    """Context is cleared after exiting mock_context."""
    with mock_context():
        pass

    with pytest.raises(LookupError):
        get_context()


def test_mock_context_request_id():
    """mock_context provides a default request_id."""
    with mock_context() as ctx:
        assert ctx.request_id is not None
        assert isinstance(ctx.request_id, str)


def test_mock_context_custom_request_id():
    """mock_context accepts custom request_id."""
    with mock_context(request_id="test-123") as ctx:
        assert ctx.request_id == "test-123"


@pytest.mark.anyio
async def test_mock_context_logging_methods():
    """Logging methods don't raise in mock context."""
    with mock_context() as ctx:
        # These should not raise
        await ctx.info("test info")
        await ctx.debug("test debug")
        await ctx.warning("test warning")
        await ctx.error("test error")


@pytest.mark.anyio
async def test_mock_context_captures_logs():
    """mock_context captures log messages for assertions."""
    with mock_context() as ctx:
        await ctx.info("hello")
        await ctx.debug("world", data={"key": "value"})

    assert len(ctx.captured_logs) == 2
    assert ctx.captured_logs[0] == ("info", "hello", None)
    assert ctx.captured_logs[1] == ("debug", "world", {"key": "value"})


@pytest.mark.anyio
async def test_mock_context_with_tool():
    """mock_context works with @tool decorated functions."""

    @tool(description="Test tool")
    async def my_tool() -> str:
        ctx = get_context()
        await ctx.info("tool called")
        return "done"

    with mock_context() as ctx:
        # @tool returns the original function, call it directly
        result = await my_tool()
        assert result == "done"
        assert len(ctx.captured_logs) == 1
        assert ctx.captured_logs[0][1] == "tool called"


def test_mock_context_nested():
    """Nested mock_context restores outer context."""
    with mock_context(request_id="outer") as outer:
        assert get_context().request_id == "outer"

        with mock_context(request_id="inner") as inner:
            assert get_context().request_id == "inner"

        assert get_context().request_id == "outer"


@pytest.mark.anyio
async def test_mock_context_progress_noop():
    """Progress methods don't raise in mock context."""
    with mock_context() as ctx:
        await ctx.report_progress(0.5, total=1.0, message="halfway")
        # Should not raise
