#!/usr/bin/env python3
# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""
North Star: End-to-end MCP server with credential provisioning.

Usage:
    export GITHUB_TOKEN="ghp_..."
    python examples/north_star.py
"""

from __future__ import annotations

import asyncio
import os

from pydantic import BaseModel

from dedalus_mcp import HttpMethod, HttpRequest, MCPServer, get_context, tool
from dedalus_mcp.auth import Connection, Credential, Credentials


# --- Response Models ---------------------------------------------------------

class UserProfile(BaseModel):
    """GitHub user profile response."""

    login: str
    name: str | None = None


class Repository(BaseModel):
    """GitHub repository summary."""

    name: str
    stars: int


class ErrorResponse(BaseModel):
    """Error response wrapper."""

    msg: str


# --- Define connections (what credentials are needed) ------------------------

github = Connection("github", credentials=Credentials(token="GITHUB_TOKEN"), base_url="https://api.github.com")

# --- Define server and tools -------------------------------------------------

server = MCPServer(name="github-tools", connections=[github])


@tool(description="Get authenticated user profile")
async def whoami() -> UserProfile | ErrorResponse:
    ctx = get_context()

    request = HttpRequest(method=HttpMethod.GET, path="/user")
    response = await ctx.dispatch(request=request)

    if response.success:
        u = response.response.body
        return UserProfile(login=u.get("login", ""), name=u.get("name"))

    msg = response.error.message if response.error else "Unknown error"
    return ErrorResponse(msg=msg)


@tool(description="List user repositories")
async def list_repos(per_page: int = 5) -> list[Repository]:
    ctx = get_context()

    request = HttpRequest(
        method=HttpMethod.GET,
        path=f"/user/repos?per_page={per_page}&sort=updated",
    )
    response = await ctx.dispatch(request=request)

    if response.success:
        return [
            Repository(name=r.get("name", ""), stars=r.get("stargazers_count", 0))
            for r in response.response.body
        ]

    return []


server.collect(whoami, list_repos)

# --- SDK initialization -------------------------------------------------------

async def main() -> None:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("Set GITHUB_TOKEN and re-run")
        return

    # Bind credential values to connection
    github_cred = Credential(github, token=token)

    print(f"Server: {server.name}")
    print(f"Tools: {server.tool_names}")
    print(f"Connections: {list(server.connections.keys())}")

    # ---------------------------------------------------------------------------
    # Full flow (when AS/Enclave are running):
    #
    #   from dedalus_labs import Dedalus
    #
    #   client = Dedalus(
    #       api_key="dsk_xxx",
    #       mcp_servers=[server],
    #       credentials=[github_cred],
    #   )
    #
    #   response = await client.chat.completions.create(
    #       model="gpt-4",
    #       messages=[{"role": "user", "content": "Who am I on GitHub?"}],
    #   )
    # ---------------------------------------------------------------------------

    print("\nReady for AS/Enclave integration")


if __name__ == "__main__":
    asyncio.run(main())
