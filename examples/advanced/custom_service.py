# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Custom capability service injection.

Demonstrates how to extend MCPServer with custom capability services that
integrate with the MCP protocol lifecycle. Useful for adding experimental
capabilities or domain-specific protocol extensions.

Pattern:
1. Define a service class with domain-specific logic
2. Subclass MCPServer and inject service in __init__
3. Wrap existing service methods to intercept calls
4. Advertise custom capabilities in experimental_capabilities

When to use this pattern:
- Application performance monitoring (APM)
- Rate limiting and quota enforcement
- SLA tracking and alerting
- Custom telemetry or audit logging

Reference:
    - Service architecture: src/openmcp/server/services/
    - Capability negotiation: https://modelcontextprotocol.io/specification/2025-06-18/basic/lifecycle
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from openmcp import MCPServer, tool
from openmcp.types import CallToolResult

# Suppress SDK and server logs for cleaner demo output
for logger_name in ("mcp", "httpx", "uvicorn", "uvicorn.access", "uvicorn.error"):
    logging.getLogger(logger_name).setLevel(logging.CRITICAL)


@dataclass
class MetricsSnapshot:
    """Aggregated metrics for server monitoring."""

    tools_called: int
    average_latency_ms: float
    error_rate: float


class MetricsService:
    """Custom capability service for server metrics collection."""

    def __init__(self) -> None:
        self._tool_calls: dict[str, int] = {}
        self._total_latency_ms: float = 0.0
        self._request_count: int = 0
        self._error_count: int = 0

    def record_tool_call(self, tool_name: str, latency_ms: float, error: bool = False) -> None:
        """Record a tool invocation."""
        self._tool_calls[tool_name] = self._tool_calls.get(tool_name, 0) + 1
        self._total_latency_ms += latency_ms
        self._request_count += 1
        if error:
            self._error_count += 1

    def snapshot(self) -> MetricsSnapshot:
        """Return current metrics snapshot."""
        avg_latency = self._total_latency_ms / self._request_count if self._request_count > 0 else 0.0
        error_rate = self._error_count / self._request_count if self._request_count > 0 else 0.0
        return MetricsSnapshot(
            tools_called=sum(self._tool_calls.values()),
            average_latency_ms=avg_latency,
            error_rate=error_rate,
        )

    def reset(self) -> None:
        """Reset all counters (useful for windowed metrics)."""
        self._tool_calls.clear()
        self._total_latency_ms = 0.0
        self._request_count = 0
        self._error_count = 0


class ExtendedMCPServer(MCPServer):
    """MCPServer with injected metrics capability."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.metrics = MetricsService()

        # Wrap existing tool service to intercept calls
        original_call_tool = self.tools.call_tool

        async def wrapped_call_tool(name: str, arguments: dict[str, Any]) -> CallToolResult:
            """Intercept tool calls for metrics collection."""
            import time

            start_ms = time.perf_counter() * 1000
            error = False
            try:
                result = await original_call_tool(name, arguments)
                error = result.isError
                return result
            finally:
                elapsed_ms = (time.perf_counter() * 1000) - start_ms
                self.metrics.record_tool_call(name, elapsed_ms, error=error)

        self.tools.call_tool = wrapped_call_tool  # type: ignore


async def main() -> None:
    """Demonstrate custom service integration."""
    server = ExtendedMCPServer(
        "metrics-demo",
        instructions="Server with metrics capability",
        experimental_capabilities={"metrics": {"version": "0.1.0"}},
    )

    with server.binding():

        @tool(description="Compute fibonacci number")
        async def fibonacci(n: int) -> int:
            """Fibonacci computation (intentionally synchronous for demo)."""
            if n <= 1:
                return n
            a, b = 0, 1
            for _ in range(2, n + 1):
                a, b = b, a + b
            return b

        @tool(description="Get current metrics")
        async def get_metrics() -> dict[str, Any]:
            """Return current server metrics snapshot."""
            snapshot = server.metrics.snapshot()
            return {
                "tools_called": snapshot.tools_called,
                "average_latency_ms": snapshot.average_latency_ms,
                "error_rate": snapshot.error_rate,
            }

    await server.serve(port=8000, verbose=False)


if __name__ == "__main__":
    print("Custom service example: MCP server with metrics capability")
    print("Tools: fibonacci, get_metrics")
    asyncio.run(main())
