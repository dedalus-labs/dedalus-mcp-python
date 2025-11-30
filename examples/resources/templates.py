# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""URI templates for parameterized resources.

Demonstrates RFC 6570 URI templates: advertise patterns like
user://{username}/profile, then register concrete resources matching those
patterns. Enables discoverable, RESTful resource hierarchies.

Pattern:
- @resource_template(uri_template="...") advertises pattern
- @resource(uri="...") registers concrete instances
- Clients see templates via resources/templates/list
- Clients read resources via resources/read with concrete URI

When to use:
- RESTful resource hierarchies (users, projects, files)
- Dynamic resource discovery
- Convention-based resource organization
- API documentation endpoints

Spec: https://modelcontextprotocol.io/specification/2025-06-18/server/resources
Usage: uv run python examples/resources/templates.py
"""

from __future__ import annotations

import asyncio
import json
import logging

from openmcp import MCPServer, resource, resource_template

# Suppress logs for clean demo output
for logger_name in ("mcp", "httpx", "uvicorn", "uvicorn.access", "uvicorn.error"):
    logging.getLogger(logger_name).setLevel(logging.CRITICAL)

server = MCPServer("template-resources")

# Mock database for demonstration
USER_DB = {
    "alice": {"name": "Alice Smith", "role": "engineer", "active": True},
    "bob": {"name": "Bob Jones", "role": "designer", "active": True},
}

with server.binding():

    @resource_template(
        name="user-profile",
        uri_template="user://{username}/profile",
        title="User Profile",
        description="Retrieve user profile by username",
        mime_type="application/json",
    )
    def user_template_metadata():
        """Resource template metadata.

        This decorator advertises the template pattern but doesn't handle reads.
        Register corresponding @resource handlers for actual URIs.
        """
        pass

    # Register specific resource instances matching the template
    @resource(
        uri="user://alice/profile",
        name="Alice Profile",
        mime_type="application/json",
    )
    def alice_profile() -> str:
        return json.dumps(USER_DB["alice"], indent=2)

    @resource(
        uri="user://bob/profile",
        name="Bob Profile",
        mime_type="application/json",
    )
    def bob_profile() -> str:
        return json.dumps(USER_DB["bob"], indent=2)

    @resource_template(
        name="api-endpoint",
        uri_template="api://v1/{service}/{method}",
        title="API Endpoint",
        description="Access API documentation by service and method",
    )
    def api_template_metadata():
        """Multi-parameter template example."""
        pass

    @resource(
        uri="api://v1/users/list",
        name="List Users API",
        mime_type="text/plain",
    )
    def users_list_doc() -> str:
        return "GET /api/v1/users - List all users\nReturns: JSON array of user objects"


async def main() -> None:
    await server.serve(transport="streamable-http", verbose=False, log_level="critical")


if __name__ == "__main__":
    asyncio.run(main())
