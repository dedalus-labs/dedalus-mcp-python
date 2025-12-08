#!/usr/bin/env python3
# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""
North Star Combined: Multi-connection MCP Server

Demonstrates combining multiple API connections in one server:
- Supabase for database operations
- OpenAI for AI capabilities
- Full SDK integration with AS token exchange

Usage:
    export SUPABASE_URL="https://xxx.supabase.co"
    export SUPABASE_KEY="eyJ..."
    export OPENAI_API_KEY="sk-..."
    export DEDALUS_API_KEY="dsk_..."  # For AS token exchange
    python examples/north_star_combined.py
"""

from __future__ import annotations

import asyncio
import os

from dedalus_mcp import HttpMethod, HttpRequest, MCPServer, get_context, tool
from dedalus_mcp.auth import Connection, Credential, Credentials

# ---------------------------------------------------------------------------
# 1. Define connections
# ---------------------------------------------------------------------------

supabase = Connection(
    'supabase',
    credentials=Credentials(apikey='SUPABASE_KEY'),
    base_url=os.environ.get('SUPABASE_URL', 'https://wdrhwyfjkohyppmtvhfu.supabase.co'),
)

openai = Connection(
    'openai',
    credentials=Credentials(api_key='OPENAI_API_KEY'),
    base_url=os.environ.get('OPENAI_BASE_URL', 'https://api.openai.com/v1'),
)

# ---------------------------------------------------------------------------
# 2. Define server
# ---------------------------------------------------------------------------

server = MCPServer(
    name='combined-tools',
    connections=[supabase, openai],
)

# ---------------------------------------------------------------------------
# 3. Supabase Tools
# ---------------------------------------------------------------------------


@tool(description='Query organizations from Supabase')
async def get_organizations(limit: int = 5) -> list[dict]:
    """List organizations from the database."""
    ctx = get_context()
    response = await ctx.dispatch(
        target=supabase,
        request=HttpRequest(
            method=HttpMethod.GET,
            path=f'/rest/v1/organizations?select=org_id,name,verified,created_at&limit={limit}&order=created_at.desc',
        ),
    )
    if response.success:
        return response.response.body
    return [{'error': response.error.message if response.error else 'Query failed'}]


@tool(description='Get MCP repository stats')
async def get_repo_stats() -> dict:
    """Get statistics about MCP repositories."""
    ctx = get_context()

    # Query public repos count
    response = await ctx.dispatch(
        target=supabase,
        request=HttpRequest(
            method=HttpMethod.GET,
            path='/rest/v1/mcp_repositories?select=repo_id&visibility=eq.public',
            headers={'Prefer': 'count=exact'},
        ),
    )

    public_count = len(response.response.body) if response.success else 0

    # Query total upvotes
    response2 = await ctx.dispatch(
        target=supabase,
        request=HttpRequest(
            method=HttpMethod.GET,
            path='/rest/v1/mcp_repositories?select=upvote_count',
        ),
    )

    total_upvotes = 0
    if response2.success:
        total_upvotes = sum(
            r.get('upvote_count', 0) or 0 for r in response2.response.body
        )

    return {
        'public_repositories': public_count,
        'total_upvotes': total_upvotes,
    }


# ---------------------------------------------------------------------------
# 4. OpenAI Tools
# ---------------------------------------------------------------------------


@tool(description='Generate AI response')
async def ask_ai(question: str) -> dict:
    """Ask GPT-4o-mini a question."""
    ctx = get_context()
    response = await ctx.dispatch(
        target=openai,
        request=HttpRequest(
            method=HttpMethod.POST,
            path='/chat/completions',
            body={
                'model': 'gpt-4o-mini',
                'messages': [{'role': 'user', 'content': question}],
                'max_tokens': 500,
            },
        ),
    )
    if response.success:
        return {
            'answer': response.response.body['choices'][0]['message']['content'],
            'model': response.response.body['model'],
        }
    return {'error': response.error.message if response.error else 'AI request failed'}


# ---------------------------------------------------------------------------
# 5. Combined Tools (use both connections)
# ---------------------------------------------------------------------------


@tool(description='Analyze organization data with AI')
async def analyze_org_data() -> dict:
    """Fetch org data from Supabase and analyze with OpenAI."""
    ctx = get_context()

    # Step 1: Get organizations from Supabase
    db_response = await ctx.dispatch(
        target=supabase,
        request=HttpRequest(
            method=HttpMethod.GET,
            path='/rest/v1/organizations?select=name,verified,created_at&limit=10',
        ),
    )

    if not db_response.success:
        return {'error': 'Failed to fetch organizations'}

    orgs = db_response.response.body

    # Step 2: Send to OpenAI for analysis
    analysis_prompt = f"""Analyze these organizations and provide insights:
{orgs}

Provide:
1. Total count
2. Verified vs unverified ratio
3. Any patterns in naming
4. Brief summary"""

    ai_response = await ctx.dispatch(
        target=openai,
        request=HttpRequest(
            method=HttpMethod.POST,
            path='/chat/completions',
            body={
                'model': 'gpt-4o-mini',
                'messages': [{'role': 'user', 'content': analysis_prompt}],
                'max_tokens': 300,
            },
        ),
    )

    if not ai_response.success:
        return {'orgs': orgs, 'analysis_error': 'AI analysis failed'}

    return {
        'org_count': len(orgs),
        'organizations': [o.get('name') for o in orgs],
        'analysis': ai_response.response.body['choices'][0]['message']['content'],
    }


server.collect(get_organizations, get_repo_stats, ask_ai, analyze_org_data)

# ---------------------------------------------------------------------------
# 6. Main entry point
# ---------------------------------------------------------------------------


async def main():
    supabase_url = os.environ.get('SUPABASE_URL')
    supabase_key = os.environ.get('SUPABASE_KEY') or os.environ.get('SUPABASE_ANON_KEY')
    openai_key = os.environ.get('OPENAI_API_KEY')
    dedalus_key = os.environ.get('DEDALUS_API_KEY')

    missing = []
    if not supabase_url:
        missing.append('SUPABASE_URL')
    if not supabase_key:
        missing.append('SUPABASE_KEY')
    if not openai_key:
        missing.append('OPENAI_API_KEY')

    if missing:
        print(f'Missing environment variables: {", ".join(missing)}')
        return

    # Bind credentials to connections
    credentials = [
        Credential(supabase, apikey=supabase_key),
        Credential(openai, api_key=openai_key),
    ]

    print(f'Server: {server.name}')
    print(f'Tools: {server.tool_names}')
    print(f'Connections: {list(server.connections.keys())}')
    print(f'Supabase: {supabase_url}')
    print(f'OpenAI: {openai.base_url}')

    # ---------------------------------------------------------------------------
    # Full SDK flow with AS token exchange
    # ---------------------------------------------------------------------------

    if dedalus_key:
        print(f'\nDedalus API key found - ready for full integration')
        print('Example SDK usage:')
        print("""
    from dedalus_labs import Dedalus

    client = Dedalus(
        api_key=os.environ["DEDALUS_API_KEY"],
        mcp_servers=[server],
        credentials=credentials,
    )

    # The SDK will:
    # 1. Exchange API key for JWT via AS token exchange
    # 2. Encrypt credentials with AS public key
    # 3. Register connections via AS /connections endpoint
    # 4. Inject connection handles into server runtime

    response = await client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "Analyze the org data"}],
    )
""")
    else:
        print('\nSet DEDALUS_API_KEY for full AS/Enclave integration')

    print('\nServer ready!')


if __name__ == '__main__':
    asyncio.run(main())
