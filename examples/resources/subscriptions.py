# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Resource subscriptions with change notifications.

Demonstrates push-based resource updates: clients subscribe to resources via
resources/subscribe, server broadcasts notifications/resources/updated when
content changes. Enables real-time data feeds without polling.

Pattern:
- Client calls resources/subscribe with URI
- Server tracks subscribers per URI
- Server calls notify_resource_updated(uri) on changes
- All subscribers receive notifications/resources/updated
- Clients re-fetch via resources/read

When to use:
- Real-time status dashboards
- Live metrics or counters
- File watchers or log tailing
- Push notifications for data changes

Spec: https://modelcontextprotocol.io/specification/2025-06-18/server/resources
Usage: uv run python examples/resources/subscriptions.py
"""

from __future__ import annotations

import asyncio
import logging

from openmcp import MCPServer, resource

# Suppress logs for clean demo output
for logger_name in ("mcp", "httpx", "uvicorn", "uvicorn.access", "uvicorn.error"):
    logging.getLogger(logger_name).setLevel(logging.CRITICAL)

server = MCPServer("subscription-resources")

# Mutable state that changes over time
_STATUS = {"state": "idle", "last_updated": "2025-01-01T00:00:00Z"}


with server.binding():

    @resource(
        uri="system://status",
        name="System Status",
        description="Current system state (subscribable)",
        mime_type="application/json",
    )
    def system_status() -> str:
        """Resource that clients can subscribe to for updates.

        When content changes, call server.notify_resource_updated(uri) to
        broadcast notifications/resources/updated to all subscribers.
        """
        import json
        return json.dumps(_STATUS, indent=2)

    @resource(
        uri="metrics://counter",
        name="Request Counter",
        description="Increments on each read (subscribable)",
        mime_type="text/plain",
    )
    def request_counter() -> str:
        """Resource with side effects - changes on access."""
        _STATUS["counter"] = _STATUS.get("counter", 0) + 1
        return f"Counter: {_STATUS['counter']}"


async def simulate_updates():
    """Background task simulating resource updates."""
    await asyncio.sleep(2)  # Wait for server startup

    states = ["processing", "ready", "idle"]
    for state in states:
        await asyncio.sleep(3)
        _STATUS["state"] = state
        from datetime import datetime
        _STATUS["last_updated"] = datetime.now().isoformat()

        # Notify all subscribers that system://status changed
        await server.notify_resource_updated("system://status")


async def main() -> None:
    asyncio.create_task(simulate_updates())
    await server.serve(transport="streamable-http", verbose=False, log_level="critical")


if __name__ == "__main__":
    asyncio.run(main())
