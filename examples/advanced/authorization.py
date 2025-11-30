# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""OAuth 2.1 authorization flow stub.

Production-ready interface stub for OAuth 2.1 protected resource pattern.
Full implementation pending PLA-26 (authorization server) and PLA-27 (token
introspection client).

Pattern:
1. Configure AuthorizationConfig with required scopes
2. Implement AuthorizationProvider for token validation
3. Set provider with server.set_authorization_provider()
4. Access authorization context in tools via get_context()

When to use this pattern:
- Multi-tenant servers requiring per-user authentication
- Plan-based feature gating (free/pro/enterprise)
- Compliance requirements (HIPAA, SOC2, GDPR)
- API access control and rate limiting

Reference:
    - Authorization config: src/openmcp/server/authorization.py
    - OAuth 2.1: https://datatracker.ietf.org/doc/html/draft-ietf-oauth-v2-1-11
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from openmcp import MCPServer, tool
from openmcp.server.authorization import (
    AuthorizationConfig,
    AuthorizationContext,
    AuthorizationError,
    AuthorizationProvider,
)

# Suppress SDK and server logs for cleaner demo output
for logger_name in ("mcp", "httpx", "uvicorn", "uvicorn.access", "uvicorn.error"):
    logging.getLogger(logger_name).setLevel(logging.CRITICAL)


class TokenIntrospectionProvider(AuthorizationProvider):
    """Production authorization provider using token introspection (RFC 7662).

    Implementation stub - production version would call real introspection endpoint.
    """

    def __init__(self, introspection_endpoint: str, client_id: str, client_secret: str) -> None:
        self.introspection_endpoint = introspection_endpoint
        self.client_id = client_id
        self.client_secret = client_secret
        self._token_cache: dict[str, tuple[AuthorizationContext, float]] = {}

    async def validate(self, token: str) -> AuthorizationContext:
        """Validate token via remote introspection endpoint.

        Production implementation would:
        1. Check local cache for token
        2. POST to introspection endpoint with client credentials
        3. Parse introspection response (active, scope, sub, exp)
        4. Cache result with TTL
        5. Return AuthorizationContext or raise AuthorizationError
        """
        # Check cache
        if token in self._token_cache:
            ctx, expiry = self._token_cache[token]
            if time.time() < expiry:
                return ctx

        # STUB: Simulated introspection response
        if token.startswith("valid-"):
            introspection = {
                "active": True,
                "scope": "mcp:read mcp:write",
                "sub": "user-123",
                "exp": int(time.time()) + 3600,
            }
        else:
            introspection = {"active": False}

        if not introspection.get("active"):
            raise AuthorizationError("Token is not active")

        # Extract context
        ctx = AuthorizationContext(
            subject=introspection.get("sub"),
            scopes=introspection.get("scope", "").split(),
            claims={"exp": introspection.get("exp")},
        )

        # Cache with TTL
        cache_ttl = min(introspection["exp"] - int(time.time()), 300)
        self._token_cache[token] = (ctx, time.time() + cache_ttl)
        return ctx


async def main() -> None:
    """Demonstrate OAuth 2.1 protected resource pattern."""
    server = MCPServer(
        "oauth-protected-server",
        instructions="OAuth 2.1 protected MCP server",
        authorization=AuthorizationConfig(
            enabled=True,
            authorization_servers=["https://as.dedaluslabs.ai"],
            required_scopes=["mcp:read", "mcp:write"],
            metadata_path="/.well-known/oauth-protected-resource",
            cache_ttl=300,
        ),
    )

    provider = TokenIntrospectionProvider(
        introspection_endpoint="https://as.dedaluslabs.ai/introspect",
        client_id="mcp-server-001",
        client_secret="secret-from-env",
    )
    server.set_authorization_provider(provider)

    with server.binding():

        @tool(description="Read user data (requires mcp:read scope)")
        async def read_data(user_id: str) -> dict[str, Any]:
            """Access control enforced by framework via required_scopes."""
            return {"user_id": user_id, "data": "sensitive information"}

        @tool(description="Write user data (requires mcp:write scope)")
        async def write_data(user_id: str, data: dict[str, Any]) -> str:
            """Fine-grained access control example."""
            return f"Data written for {user_id}"

    await server.serve(port=8000, verbose=False)


if __name__ == "__main__":
    print("OAuth 2.1 authorization example (interface stub)")
    print("Full implementation pending: PLA-26 (auth server), PLA-27 (introspection)")
    print('Test: curl -H "Authorization: Bearer valid-demo-token" http://localhost:8000/mcp')
    asyncio.run(main())
