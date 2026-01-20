# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Server that requests user input from the client.

Elicitation enables servers to ask clients for user input during
tool execution. This is useful for:

- Confirmation dialogs ("Are you sure?")
- Interactive forms (collect additional info)
- Approval workflows (human-in-the-loop)
- Disambiguation ("Which one did you mean?")

Usage:
    # Terminal 1:
    uv run python examples/capabilities/elicitation/server.py

    # Terminal 2:
    uv run python examples/capabilities/elicitation/client.py
"""

import asyncio
import logging

from dedalus_mcp import MCPServer, get_context, tool
from dedalus_mcp.types import ElicitRequestParams


for name in ("mcp", "httpx", "uvicorn"):
    logging.getLogger(name).setLevel(logging.WARNING)

server = MCPServer("elicitation-demo", instructions="I may ask for user confirmation")


@tool(description="Delete a file (requires confirmation)")
async def delete_file(path: str) -> dict:
    """Ask user to confirm before deleting."""
    ctx = get_context()
    mcp = ctx.server
    if not mcp:
        return {"error": "Server context not available"}

    await ctx.info(f"Requesting confirmation to delete: {path}")

    # Ask for confirmation
    params = ElicitRequestParams(
        message=f"Are you sure you want to delete '{path}'? This cannot be undone.",
        requestedSchema={
            "type": "object",
            "properties": {"confirmed": {"type": "boolean", "description": "Confirm deletion"}},
            "required": ["confirmed"],
        },
    )

    response = await mcp.request_elicitation(params)

    if response.action == "accept" and response.content.get("confirmed"):
        # User confirmed — perform deletion
        await ctx.info(f"Deletion confirmed for: {path}")
        return {"deleted": True, "path": path}
    # User declined
    await ctx.info("Deletion cancelled by user")
    return {"deleted": False, "path": path, "reason": "User cancelled"}


@tool(description="Create a user account (collects info)")
async def create_account(email: str) -> dict:
    """Elicit additional user information."""
    ctx = get_context()
    mcp = ctx.server
    if not mcp:
        return {"error": "Server context not available"}

    await ctx.info(f"Collecting account details for: {email}")

    # Collect additional info
    params = ElicitRequestParams(
        message=f"Complete account setup for {email}",
        requestedSchema={
            "type": "object",
            "properties": {
                "display_name": {"type": "string", "description": "Your display name"},
                "role": {"type": "string", "enum": ["developer", "designer", "manager", "other"]},
                "newsletter": {"type": "boolean", "description": "Subscribe to newsletter", "default": False},
            },
            "required": ["display_name", "role"],
        },
    )

    response = await mcp.request_elicitation(params)

    if response.action == "accept":
        return {
            "created": True,
            "email": email,
            "display_name": response.content.get("display_name"),
            "role": response.content.get("role"),
            "newsletter": response.content.get("newsletter", False),
        }
    return {"created": False, "email": email, "reason": "User cancelled setup"}


@tool(description="Deploy to environment (requires approval)")
async def deploy(environment: str, version: str) -> dict:
    """Human-in-the-loop approval for deployments."""
    ctx = get_context()
    mcp = ctx.server
    if not mcp:
        return {"error": "Server context not available"}

    risk_level = "HIGH" if environment == "production" else "MEDIUM"
    await ctx.warning(f"Deployment requested: {version} → {environment} (Risk: {risk_level})")

    params = ElicitRequestParams(
        message=f"⚠️ Deploy {version} to {environment}?\n\nRisk Level: {risk_level}",
        requestedSchema={
            "type": "object",
            "properties": {
                "approved": {"type": "boolean", "description": "Approve this deployment"},
                "reason": {"type": "string", "description": "Reason for approval/rejection"},
            },
            "required": ["approved"],
        },
    )

    response = await mcp.request_elicitation(params)

    if response.action == "accept" and response.content.get("approved"):
        await ctx.info(f"Deployment approved: {response.content.get('reason', 'No reason given')}")
        return {
            "deployed": True,
            "environment": environment,
            "version": version,
            "approved_by": "user",
            "reason": response.content.get("reason"),
        }
    await ctx.info(f"Deployment rejected: {response.content.get('reason', 'No reason given')}")
    return {
        "deployed": False,
        "environment": environment,
        "version": version,
        "reason": response.content.get("reason", "User rejected"),
    }


server.collect(delete_file, create_account, deploy)

if __name__ == "__main__":
    print("Elicitation Demo Server: http://127.0.0.1:8000/mcp")
    print("\nTools that request user input:")
    print("  delete_file    - Confirmation dialog")
    print("  create_account - Form input collection")
    print("  deploy         - Approval workflow")
    print("\nRun the client to see elicitation in action!")
    asyncio.run(server.serve())
