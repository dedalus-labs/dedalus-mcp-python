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

from dedalus_mcp import HttpMethod, HttpRequest, MCPServer, get_context, tool
from dedalus_mcp.auth import Connection, Credential, Credentials

# ---------------------------------------------------------------------------
# 1. Define connections (what credentials are needed)
# ---------------------------------------------------------------------------

github = Connection(
    'github',
    credentials=Credentials(token='GITHUB_TOKEN'),
    base_url='https://api.github.com',
)

# ---------------------------------------------------------------------------
# 2. Define server and tools
# ---------------------------------------------------------------------------

server = MCPServer(name='github-tools', connections=[github])


@tool(description='Get authenticated user profile')
async def whoami() -> dict:
    ctx = get_context()
    response = await ctx.dispatch(HttpRequest(method=HttpMethod.GET, path='/user'))
    if response.success:
        u = response.response.body
        return {'login': u.get('login'), 'name': u.get('name')}
    return {'error': response.error.message}


@tool(description='List user repositories')
async def list_repos(per_page: int = 5) -> list:
    ctx = get_context()
    response = await ctx.dispatch(
        HttpRequest(
            method=HttpMethod.GET, path=f'/user/repos?per_page={per_page}&sort=updated'
        )
    )
    if response.success:
        return [
            {'name': r.get('name'), 'stars': r.get('stargazers_count')}
            for r in response.response.body
        ]
    return []


server.collect(whoami, list_repos)

# ---------------------------------------------------------------------------
# 3. SDK initialization
# ---------------------------------------------------------------------------


async def main():
    token = os.environ.get('GITHUB_TOKEN')
    if not token:
        print('Set GITHUB_TOKEN and re-run')
        return

    # Bind credential values to connection
    github_cred = Credential(github, token=token)

    print(f'Server: {server.name}')
    print(f'Tools: {server.tool_names}')
    print(f'Connections: {list(server.connections.keys())}')

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

    print('\nReady for AS/Enclave integration')


if __name__ == '__main__':
    asyncio.run(main())
