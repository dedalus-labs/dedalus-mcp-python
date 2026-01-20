# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Server with live-updating resources.

Resources can push updates to subscribed clients. This example
simulates a live stock ticker and system metrics dashboard.

Clients subscribe to resources and receive updates via
`notifications/resources/updated`.

Usage:
    uv run python examples/showcase/04_live_resources_server.py
"""

import asyncio
from datetime import datetime
import random

from dedalus_mcp import MCPServer, get_context, resource, tool


server = MCPServer("live-resources", instructions="Subscribe to live data feeds")


# Simulated live data
stock_prices = {"AAPL": 175.50, "GOOGL": 140.25, "MSFT": 380.00}
system_metrics = {"cpu": 45.0, "memory": 62.0, "requests_per_sec": 1250}


@resource(uri="stocks://prices", description="Live stock prices")
def get_stock_prices() -> dict:
    return {"timestamp": datetime.now().isoformat(), "prices": stock_prices.copy()}


@resource(uri="system://metrics", description="Live system metrics")
def get_system_metrics() -> dict:
    return {"timestamp": datetime.now().isoformat(), "metrics": system_metrics.copy()}


@resource(uri="stocks://price/{symbol}", description="Single stock price")
def get_stock_price(symbol: str) -> dict:
    price = stock_prices.get(symbol.upper())
    if price is None:
        return {"error": f"Unknown symbol: {symbol}"}
    return {"symbol": symbol.upper(), "price": price, "timestamp": datetime.now().isoformat()}


@tool(description="Subscribe to a resource for live updates")
async def subscribe(uri: str) -> dict:
    """Client subscribes to receive updates for this resource."""
    ctx = get_context()
    # In a real implementation, you'd track subscriptions per session
    await ctx.info(f"Subscribed to: {uri}")
    return {"subscribed": uri, "message": "You'll receive updates when this resource changes"}


server.collect(get_stock_prices, get_system_metrics, get_stock_price, subscribe)


async def simulate_market() -> None:
    """Simulate market movements and push updates."""
    while True:
        await asyncio.sleep(2)

        # Random price movements
        for symbol in stock_prices:
            change = random.uniform(-2.0, 2.0)
            stock_prices[symbol] = round(stock_prices[symbol] + change, 2)

        # Random metric changes
        system_metrics["cpu"] = round(random.uniform(20, 80), 1)
        system_metrics["memory"] = round(random.uniform(50, 90), 1)
        system_metrics["requests_per_sec"] = random.randint(800, 2000)

        # Notify subscribers
        await server.notify_resources_list_changed()


async def main() -> None:
    print("Starting live resources server...")
    print("MCP endpoint: http://127.0.0.1:8000/mcp")
    print("\nResources:")
    print("  stocks://prices      - All stock prices")
    print("  system://metrics     - System metrics")
    print("  stocks://price/AAPL  - Single stock\n")

    # Start market simulation in background
    asyncio.create_task(simulate_market())

    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
