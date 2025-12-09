#!/usr/bin/env python3
# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""
North Star: Supabase MCP Server (Supabase-ception!)

Wraps Supabase REST API as MCP tools, demonstrating:
- Connection/Credential pattern for API key management
- ctx.dispatch() for authenticated HTTP requests
- Real database operations through the dispatch layer

Usage:
    export SUPABASE_URL="https://xxx.supabase.co"
    export SUPABASE_KEY="eyJ..."  # anon or service_role key
    python examples/north_star_supabase.py
"""

from __future__ import annotations

import asyncio
import os

from dedalus_mcp import HttpMethod, HttpRequest, MCPServer, get_context, tool
from dedalus_mcp.auth import Connection, Credential, Credentials

# ---------------------------------------------------------------------------
# 1. Define Supabase connection
# ---------------------------------------------------------------------------

supabase = Connection(
    'supabase',
    credentials=Credentials(apikey='SUPABASE_KEY'),
    base_url=os.environ.get('SUPABASE_URL', 'https://wdrhwyfjkohyppmtvhfu.supabase.co'),
)


# ---------------------------------------------------------------------------
# 2. Define server and tools
# ---------------------------------------------------------------------------

server = MCPServer(name='supabase-tools', connections=[supabase])


@tool(description='List all tables in the public schema')
async def list_tables() -> list[dict]:
    """Query pg_tables via PostgREST to list available tables."""
    ctx = get_context()
    response = await ctx.dispatch(
        HttpRequest(
            method=HttpMethod.GET,
            path='/rest/v1/rpc/get_tables',
            headers={'Prefer': 'return=representation'},
        )
    )
    if response.success:
        return response.response.body
    # Fallback: query information_schema directly
    return [{'error': response.error.message if response.error else 'Unknown error'}]


@tool(description='Query a table with optional filters')
async def query_table(
    table: str,
    select: str = '*',
    limit: int = 10,
    filter_column: str | None = None,
    filter_value: str | None = None,
) -> list[dict]:
    """Query any Supabase table via PostgREST.

    Args:
        table: Table name (e.g., 'users', 'organizations')
        select: Columns to select (default '*')
        limit: Max rows to return (default 10)
        filter_column: Optional column to filter on
        filter_value: Optional value to filter by (uses eq)
    """
    ctx = get_context()

    # Build query path
    path = f'/rest/v1/{table}?select={select}&limit={limit}'
    if filter_column and filter_value:
        path += f'&{filter_column}=eq.{filter_value}'

    response = await ctx.dispatch(
        HttpRequest(
            method=HttpMethod.GET,
            path=path,
            headers={'Prefer': 'return=representation'},
        )
    )
    if response.success:
        return response.response.body
    return [{'error': response.error.message if response.error else 'Query failed'}]


@tool(description='Count rows in a table')
async def count_rows(table: str) -> dict:
    """Get row count for a table."""
    ctx = get_context()
    response = await ctx.dispatch(
        HttpRequest(
            method=HttpMethod.GET,
            path=f'/rest/v1/{table}?select=count',
            headers={'Prefer': 'count=exact'},
        )
    )
    if response.success:
        # PostgREST returns count in content-range header
        return {'table': table, 'count': len(response.response.body)}
    return {'error': response.error.message if response.error else 'Count failed'}


@tool(description='Get organization details by name')
async def get_organization(name: str) -> dict:
    """Look up an organization by name."""
    ctx = get_context()
    response = await ctx.dispatch(
        HttpRequest(
            method=HttpMethod.GET,
            path=f'/rest/v1/organizations?name=eq.{name}&select=org_id,name,verified,created_at',
        )
    )
    if response.success and response.response.body:
        return response.response.body[0]
    return {'error': 'Organization not found'}


@tool(description='List recent API key events')
async def list_api_key_events(limit: int = 5) -> list[dict]:
    """Get recent API key events for audit."""
    ctx = get_context()
    response = await ctx.dispatch(
        HttpRequest(
            method=HttpMethod.GET,
            path=f'/rest/v1/api_key_events?select=event_type,created_at,old_status,new_status&order=created_at.desc&limit={limit}',
        )
    )
    if response.success:
        return response.response.body
    return [{'error': response.error.message if response.error else 'Query failed'}]


server.collect(
    list_tables, query_table, count_rows, get_organization, list_api_key_events
)

# ---------------------------------------------------------------------------
# 3. SDK initialization
# ---------------------------------------------------------------------------


async def main():
    url = os.environ.get('SUPABASE_URL')
    key = os.environ.get('SUPABASE_KEY') or os.environ.get('SUPABASE_ANON_KEY')

    if not url or not key:
        print('Set SUPABASE_URL and SUPABASE_KEY (or SUPABASE_ANON_KEY)')
        return

    # Bind credential to connection
    supabase_cred = Credential(supabase, apikey=key)

    print(f'Server: {server.name}')
    print(f'Tools: {server.tool_names}')
    print(f'Connections: {list(server.connections.keys())}')
    print(f'Supabase URL: {url}')

    # ---------------------------------------------------------------------------
    # Full flow (when AS/Enclave are running):
    #
    #   from dedalus_labs import Dedalus
    #
    #   client = Dedalus(
    #       api_key="dsk_xxx",
    #       mcp_servers=[server],
    #       credentials=[supabase_cred],
    #   )
    #
    #   response = await client.chat.completions.create(
    #       model="gpt-4",
    #       messages=[{"role": "user", "content": "How many organizations are in the database?"}],
    #   )
    # ---------------------------------------------------------------------------

    print('\nReady for AS/Enclave integration')


if __name__ == '__main__':
    asyncio.run(main())
