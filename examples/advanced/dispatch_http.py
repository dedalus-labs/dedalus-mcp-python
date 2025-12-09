# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""HTTP dispatch interface for MCP servers.

This example demonstrates the Connection + HttpRequest dispatch model:

1. Define Connection objects declaring external service dependencies
2. Pass connections to MCPServer at construction
3. Use ctx.dispatch(HttpRequest(...)) in tools to make authenticated requests
4. Framework resolves connections to handles and routes through enclave

The dispatch model provides:
- Type-safe HTTP requests with validation
- Automatic credential injection via enclave
- Connection resolution (name → handle) at runtime
- Clear separation: MCP server declares *what* to call, enclave handles *credentials*
"""

from __future__ import annotations

from dedalus_mcp import (
    Connection,
    Credentials,
    HttpMethod,
    HttpRequest,
    MCPServer,
    get_context,
    tool,
)


# =============================================================================
# Single Connection Server
# =============================================================================


def create_github_server() -> MCPServer:
    """Server with single connection - target is implicit in dispatch."""

    github = Connection(
        'github',
        credentials=Credentials(token='GITHUB_TOKEN'),
        base_url='https://api.github.com',
        timeout_ms=30_000,
    )

    server = MCPServer(name='github-tools', connections=[github])

    @tool(description='Get authenticated user info')
    async def get_user() -> dict:
        ctx = get_context()
        # Single connection: target is implicit
        response = await ctx.dispatch(HttpRequest(method=HttpMethod.GET, path='/user'))
        if response.success:
            return response.response.body
        return {'error': response.error.message}

    @tool(description='List user repositories')
    async def list_repos(per_page: int = 30) -> list:
        ctx = get_context()
        response = await ctx.dispatch(
            HttpRequest(
                method=HttpMethod.GET,
                path=f'/user/repos?per_page={per_page}',
            )
        )
        if response.success:
            return response.response.body
        return []

    @tool(description='Create a GitHub issue')
    async def create_issue(owner: str, repo: str, title: str, body: str = '') -> dict:
        ctx = get_context()
        response = await ctx.dispatch(
            HttpRequest(
                method=HttpMethod.POST,
                path=f'/repos/{owner}/{repo}/issues',
                body={'title': title, 'body': body},
                headers={'Accept': 'application/vnd.github+json'},
            )
        )
        if response.success:
            return {'issue_number': response.response.body.get('number')}
        return {'error': response.error.message}

    server.collect(get_user, list_repos, create_issue)
    return server


# =============================================================================
# Multi-Connection Server
# =============================================================================


def create_multi_api_server() -> MCPServer:
    """Server with multiple connections - target is explicit in dispatch."""

    github = Connection(
        'github',
        credentials=Credentials(token='GITHUB_TOKEN'),
        base_url='https://api.github.com',
    )

    openai = Connection(
        'openai',
        credentials=Credentials(api_key='OPENAI_API_KEY'),
        base_url='https://api.openai.com/v1',
    )

    server = MCPServer(name='multi-api', connections=[github, openai])

    @tool(description='Get GitHub user info')
    async def github_user() -> dict:
        ctx = get_context()
        # Multi-connection: explicit target by name
        response = await ctx.dispatch(
            'github',
            HttpRequest(method=HttpMethod.GET, path='/user'),
        )
        if response.success:
            return response.response.body
        return {'error': response.error.message}

    @tool(description='List OpenAI models')
    async def list_models() -> list:
        ctx = get_context()
        # Can also pass Connection object directly
        response = await ctx.dispatch(
            openai,
            HttpRequest(method=HttpMethod.GET, path='/models'),
        )
        if response.success:
            return response.response.body.get('data', [])
        return []

    server.collect(github_user, list_models)
    return server


# =============================================================================
# Error Handling
# =============================================================================


def create_robust_server() -> MCPServer:
    """Demonstrates proper error handling for dispatch responses."""

    api = Connection(
        'api',
        credentials=Credentials(key='API_KEY'),
        base_url='https://api.example.com',
    )

    server = MCPServer(name='robust-api', connections=[api])

    @tool(description='Fetch data with error handling')
    async def fetch_data(resource_id: str) -> dict:
        ctx = get_context()
        response = await ctx.dispatch(
            HttpRequest(method=HttpMethod.GET, path=f'/data/{resource_id}')
        )

        # success=True means we got an HTTP response (even 4xx/5xx)
        if response.success:
            http = response.response
            if http.status == 200:
                return {'data': http.body}
            elif http.status == 404:
                return {'error': 'not_found', 'resource_id': resource_id}
            elif http.status >= 400:
                return {'error': 'api_error', 'status': http.status}

        # success=False means infrastructure failure
        err = response.error
        if err.retryable:
            return {'error': 'retryable', 'code': err.code, 'message': err.message}
        return {'error': 'fatal', 'code': err.code, 'message': err.message}

    server.collect(fetch_data)
    return server


# =============================================================================
# Main
# =============================================================================


if __name__ == '__main__':
    print('=== HTTP Dispatch Examples ===\n')

    print('1. Single-connection server (GitHub):')
    gh = create_github_server()
    print(f'   connections: {list(gh.connections.keys())}')
    print(f'   tools: {gh.tool_names}\n')

    print('2. Multi-connection server:')
    multi = create_multi_api_server()
    print(f'   connections: {list(multi.connections.keys())}')
    print(f'   tools: {multi.tool_names}\n')

    print('3. Robust error handling:')
    robust = create_robust_server()
    print(f'   connections: {list(robust.connections.keys())}')
    print(f'   tools: {robust.tool_names}')
