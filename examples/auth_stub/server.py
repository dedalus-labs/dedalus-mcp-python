# ==============================================================================
#                  © 2025 Dedalus Labs, Inc. and affiliates
#                            Licensed under MIT
#               github.com/dedalus-labs/openmcp-python/LICENSE
# ==============================================================================

"""Authorization scaffold demo.

Demonstrates server-side authorization per docs/mcp/spec/schema-reference/authorization-*.md.
Shows how to:

1. Configure server with AuthorizationConfig (enabled, required scopes, auth servers)
2. Implement custom authorization provider (token validation)
3. Protect tool access via authorization context

The DemoProvider validates tokens against a simple allowlist. In production, this
would integrate with OAuth2/OIDC providers, validate JWTs, check scopes against
user claims, etc.

Authorization errors return standard MCP error responses per the spec, preventing
unauthorized tool execution.

Run::

    uv run python examples/auth_stub/server.py

Then call with the demo token::

    curl -H "Authorization: Bearer demo-token" http://127.0.0.1:8000/mcp

Invalid tokens receive authorization errors per the spec.
"""

from __future__ import annotations

import asyncio
import logging

from openmcp import MCPServer, tool
from openmcp.server.authorization import AuthorizationConfig, AuthorizationContext, AuthorizationError

# Suppress logs for cleaner demo output
for logger_name in ("mcp", "httpx", "uvicorn", "uvicorn.access", "uvicorn.error"):
    logging.getLogger(logger_name).setLevel(logging.CRITICAL)


server = MCPServer(
    "auth-demo",
    authorization=AuthorizationConfig(
        enabled=True, required_scopes=["mcp:read"], authorization_servers=["https://as.dedaluslabs.ai"]
    ),
)


class DemoProvider:
    """Minimal authorization provider for demonstration purposes."""

    async def validate(self, token: str) -> AuthorizationContext:
        """Validate token and return authorization context.

        Args:
            token: Bearer token from Authorization header

        Returns:
            AuthorizationContext with subject, scopes, and claims

        Raises:
            AuthorizationError: If token is invalid
        """
        if token != "demo-token":
            raise AuthorizationError("invalid token")
        return AuthorizationContext(subject="demo", scopes=["mcp:read"], claims={})


server.set_authorization_provider(DemoProvider())


with server.binding():

    @tool(description="Echoes a value")
    async def echo(value: str) -> str:
        """Echo the input value (requires authorization)."""
        return value


async def main() -> None:
    """Serve the auth-demo MCP server."""
    await server.serve(transport="streamable-http", verbose=False, log_level="critical", uvicorn_options={"access_log": False})


if __name__ == "__main__":
    asyncio.run(main())
