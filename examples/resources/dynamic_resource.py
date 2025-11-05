# ==============================================================================
#                  © 2025 Dedalus Labs, Inc. and affiliates
#                            Licensed under MIT
#               github.com/dedalus-labs/openmcp-python/LICENSE
# ==============================================================================

"""Dynamic resources with computed content.

Demonstrates resources that generate fresh data per-request: timestamps,
system metrics, database queries. Resource functions execute on every
resources/read, enabling dynamic content without subscriptions.

Pattern:
- Resource function called on each resources/read request
- Compute fresh data (query DB, read system state, generate reports)
- Use get_context() for request-scoped logging
- Return new content each time (non-deterministic)

When to use:
- Current timestamps or dates
- System metrics (memory, CPU, disk)
- Database query results
- Generated reports or summaries
- Non-cacheable dynamic data

Spec: https://modelcontextprotocol.io/specification/2025-06-18/server/resources
Usage: uv run python examples/resources/dynamic_resource.py
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime

from openmcp import MCPServer, get_context, resource

# Suppress logs for clean demo output
for logger_name in ("mcp", "httpx", "uvicorn", "uvicorn.access", "uvicorn.error"):
    logging.getLogger(logger_name).setLevel(logging.CRITICAL)

server = MCPServer("dynamic-resources")

with server.binding():

    @resource(
        uri="time://current",
        name="Current Time",
        description="Server timestamp (updates on each read)",
        mime_type="text/plain",
    )
    def current_time() -> str:
        """Resource that generates fresh content per request.

        Each resources/read call invokes this function, allowing
        dynamic computation. Use get_context() for request-scoped logging.
        """
        ctx = get_context()
        now = datetime.now().isoformat()
        # Log to client via notifications/message
        asyncio.create_task(ctx.debug("Timestamp generated", data={"time": now}))
        return f"Current time: {now}"

    @resource(
        uri="metrics://memory",
        name="Memory Usage",
        description="Current process memory metrics",
        mime_type="application/json",
    )
    def memory_metrics() -> str:
        """Query system state dynamically."""
        import os
        import psutil

        process = psutil.Process(os.getpid())
        mem_info = process.memory_info()

        metrics = {
            "rss_mb": mem_info.rss / 1024 / 1024,
            "vms_mb": mem_info.vms / 1024 / 1024,
            "percent": process.memory_percent(),
            "timestamp": datetime.now().isoformat(),
        }
        return json.dumps(metrics, indent=2)

    @resource(
        uri="data://random",
        name="Random Data",
        description="Generates random dataset on each read",
        mime_type="application/json",
    )
    def random_data() -> str:
        """Non-deterministic resource output."""
        import random

        dataset = {
            "samples": [random.random() for _ in range(10)],
            "seed": random.randint(0, 1000000),
            "generated_at": datetime.now().isoformat(),
        }
        return json.dumps(dataset, indent=2)


async def main() -> None:
    await server.serve(transport="streamable-http", verbose=False, log_level="critical")


if __name__ == "__main__":
    asyncio.run(main())
