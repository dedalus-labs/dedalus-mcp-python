# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Tool tags and allow-list filtering.

Tags organize tools into categories. Allow-lists control which tools
are exposed to clients—useful for feature flags, multi-tenant servers,
or role-based access.

Usage:
    uv run python examples/capabilities/tools/02_tags_and_filtering.py
"""

import asyncio
import logging

from dedalus_mcp import MCPServer, tool

for name in ("mcp", "httpx", "uvicorn"):
    logging.getLogger(name).setLevel(logging.WARNING)

server = MCPServer("tagged-tools", allow_dynamic_tools=True)


# Tag tools by category
@tool(description="Read from database", tags={"database", "read"})
def db_read(table: str, id: int) -> dict:
    return {"table": table, "id": id, "data": {"example": "value"}}


@tool(description="Write to database", tags={"database", "write", "dangerous"})
def db_write(table: str, data: dict) -> dict:
    return {"table": table, "written": True, "rows": 1}


@tool(description="Delete from database", tags={"database", "write", "dangerous"})
def db_delete(table: str, id: int) -> dict:
    return {"table": table, "deleted": id}


@tool(description="Send email", tags={"communication", "external"})
def send_email(to: str, subject: str, body: str) -> dict:
    return {"sent": True, "to": to, "subject": subject}


@tool(description="Send SMS", tags={"communication", "external", "paid"})
def send_sms(phone: str, message: str) -> dict:
    return {"sent": True, "phone": phone, "chars": len(message)}


@tool(description="Calculate sum", tags={"math", "safe"})
def calculate(expression: str) -> float:
    # Safe eval for demo (don't do this in production!)
    allowed = set("0123456789+-*/.()")
    if all(c in allowed or c.isspace() for c in expression):
        return eval(expression)
    raise ValueError("Invalid expression")


@tool(description="Health check", tags={"system", "safe"})
def health() -> str:
    return "ok"


server.collect(db_read, db_write, db_delete, send_email, send_sms, calculate, health)


def demo_filtering() -> None:
    """Demonstrate allow-list filtering."""
    print("\n--- Allow-list Filtering Demo ---\n")

    # Show all tools
    all_tools = server.tools.tool_names
    print(f"All tools: {all_tools}")

    # Filter to safe tools only
    safe_tools = ["db_read", "calculate", "health"]
    server.tools.allow_tools(safe_tools)
    print(f"After allow_tools({safe_tools}): {server.tools.tool_names}")

    # Filter to database tools only
    db_tools = ["db_read", "db_write", "db_delete"]
    server.tools.allow_tools(db_tools)
    print(f"After allow_tools({db_tools}): {server.tools.tool_names}")

    # Reset to all tools
    server.tools.allow_tools(None)
    print(f"After allow_tools(None): {server.tools.tool_names}")

    print("\n--- End Demo ---\n")


if __name__ == "__main__":
    demo_filtering()

    print("Tagged tools server: http://127.0.0.1:8000/mcp")
    print("\nTools by tag:")
    print("  database: db_read, db_write, db_delete")
    print("  communication: send_email, send_sms")
    print("  safe: calculate, health")
    print("  dangerous: db_write, db_delete")
    print("\nUse server.tools.allow_tools(['tool1', 'tool2']) to filter")
    asyncio.run(server.serve())
