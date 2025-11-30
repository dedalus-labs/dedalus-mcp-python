# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Sync vs async tool functions work identically.

Demonstrates framework transparency: sync functions execute directly, async
functions are awaited. No special decoration needed—type inspection at
runtime handles both cases. Use sync for CPU-bound work, async for I/O.

Pattern:
- Sync tools: def tool_name(...) -> direct execution
- Async tools: async def tool_name(...) -> awaited by framework
- Framework uses utils.maybe_await_with_args internally
- No await overhead for sync functions

When to use sync:
- Pure computation (math, string ops)
- No I/O (network, disk, subprocess)
- Sub-millisecond execution

When to use async:
- Network requests (HTTP, gRPC, database)
- File I/O or long-running operations
- Need to yield control during waits

Spec: https://modelcontextprotocol.io/specification/2025-06-18/server/tools
Usage: uv run python examples/tools/mixed_sync_async.py
"""

from __future__ import annotations

import asyncio
import logging

from openmcp import MCPServer, tool

# Suppress logs for clean demo output
for logger_name in ("mcp", "httpx", "uvicorn", "uvicorn.access", "uvicorn.error"):
    logging.getLogger(logger_name).setLevel(logging.CRITICAL)

server = MCPServer(name="mixed-sync-async-demo")


with server.binding():

    @tool(description="Synchronous computation - no I/O, CPU-bound")
    def calculate_fibonacci(n: int) -> dict[str, int]:
        """Pure function: deterministic, no side effects, instant execution.

        Use sync when:
        - Pure computation (math, string ops, data transforms)
        - No I/O (network, disk, subprocess)
        - Sub-millisecond execution time
        """
        if n < 0:
            raise ValueError("n must be non-negative")
        if n <= 1:
            return {"result": n}

        a, b = 0, 1
        for _ in range(n - 1):
            a, b = b, a + b
        return {"result": b}

    @tool(description="Synchronous validation - fast, deterministic")
    def validate_email(email: str) -> dict[str, bool | str]:
        """Simple validation logic - no async needed."""
        is_valid = "@" in email and "." in email.split("@")[-1]
        return {"valid": is_valid, "reason": "Valid format" if is_valid else "Missing @ or domain"}

    @tool(description="Asynchronous I/O - network fetch simulation")
    async def fetch_weather(city: str) -> dict[str, str | float]:
        """Network I/O requires async for concurrency.

        Use async when:
        - Network requests (HTTP, gRPC, database)
        - File I/O (reading logs, processing large files)
        - Long-running operations (>100ms)
        - Need to yield control during waits
        """
        await asyncio.sleep(0.5)  # Simulate API latency
        return {"city": city, "temperature": 72.5, "condition": "sunny", "source": "mock-api"}

    @tool(description="Asynchronous database query simulation")
    async def query_user(user_id: int) -> dict[str, str | int]:
        """Database access—inherently async. Real impl uses asyncpg, motor, etc."""
        await asyncio.sleep(0.2)  # Simulate query time
        return {"user_id": user_id, "username": f"user_{user_id}", "status": "active"}


async def main() -> None:
    print("=== Mixed Sync/Async Demo ===")
    print("Registered tools:")
    print("  - calculate_fibonacci (sync, CPU-bound)")
    print("  - validate_email (sync, pure function)")
    print("  - fetch_weather (async, network I/O)")
    print("  - query_user (async, database I/O)")
    print("\nFramework handles both transparently via same call_tool API.")
    print("Server: http://127.0.0.1:8000/mcp\n")

    await server.serve(transport="streamable-http", verbose=False, log_level="critical")


if __name__ == "__main__":
    asyncio.run(main())
