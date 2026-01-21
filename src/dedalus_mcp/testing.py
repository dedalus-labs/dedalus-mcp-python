# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Testing utilities for MCP servers.

Provides helpers to test tools, resources, and prompts without running a full server.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import Token
from dataclasses import dataclass, field
from typing import Any

from .context import _CURRENT_CONTEXT


@dataclass
class MockContext:
    """Mock context for testing tools outside of request handlers.

    Captures log messages and provides no-op implementations for progress.

    Usage:
        with mock_context() as ctx:
            result = await my_tool.impl()
            assert ctx.captured_logs[0][1] == "expected message"
    """

    _request_id: str = "test-request-1"
    captured_logs: list[tuple[str, str, dict[str, Any] | None]] = field(default_factory=list)

    @property
    def request_id(self) -> str:
        return self._request_id

    @property
    def session_id(self) -> str | None:
        return None

    @property
    def progress_token(self) -> None:
        return None

    @property
    def auth_context(self) -> None:
        return None

    @property
    def server(self) -> None:
        return None

    @property
    def resolver(self) -> None:
        return None

    async def log(
        self, level: str, message: str, *, logger: str | None = None, data: Mapping[str, Any] | None = None
    ) -> None:
        self.captured_logs.append((level, message, dict(data) if data else None))

    async def debug(self, message: str, *, logger: str | None = None, data: Mapping[str, Any] | None = None) -> None:
        await self.log("debug", message, logger=logger, data=data)

    async def info(self, message: str, *, logger: str | None = None, data: Mapping[str, Any] | None = None) -> None:
        await self.log("info", message, logger=logger, data=data)

    async def warning(self, message: str, *, logger: str | None = None, data: Mapping[str, Any] | None = None) -> None:
        await self.log("warning", message, logger=logger, data=data)

    async def error(self, message: str, *, logger: str | None = None, data: Mapping[str, Any] | None = None) -> None:
        await self.log("error", message, logger=logger, data=data)

    async def report_progress(self, progress: float, *, total: float | None = None, message: str | None = None) -> None:
        # No-op in mock context
        pass


@contextmanager
def mock_context(*, request_id: str = "test-request-1") -> Iterator[MockContext]:
    """Context manager that provides a mock context for testing.

    Makes get_context() work outside of MCP request handlers.

    Args:
        request_id: Custom request ID for the mock context.

    Example:
        from dedalus_mcp import get_context
        from dedalus_mcp.testing import mock_context

        @tool(description="Log something")
        async def my_tool() -> str:
            ctx = get_context()
            await ctx.info("hello")
            return "done"

        # Test without running a server
        with mock_context() as ctx:
            result = await my_tool.impl()
            assert ctx.captured_logs[0][1] == "hello"
    """
    ctx = MockContext(_request_id=request_id)
    token: Token[Any] = _CURRENT_CONTEXT.set(ctx)  # type: ignore[arg-type]
    try:
        yield ctx
    finally:
        _CURRENT_CONTEXT.reset(token)


__all__ = ["MockContext", "mock_context"]
