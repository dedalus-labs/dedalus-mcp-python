# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Static resources — files and data exposed to clients.

Resources are read-only data that clients can fetch. Use them for
configuration, documentation, schemas, or any static content.

Usage:
    uv run python examples/capabilities/resources/01_static_resources.py
"""

import asyncio
import logging

from dedalus_mcp import MCPServer, resource


for name in ("mcp", "httpx", "uvicorn"):
    logging.getLogger(name).setLevel(logging.WARNING)

server = MCPServer("static-resources")


# Plain text resource
@resource(uri="config://app/readme", name="README", mime_type="text/plain")
def readme() -> str:
    return """Welcome to the Example App

This MCP server exposes configuration and documentation as resources.

Available resources:
- config://app/readme - This file
- config://app/settings - Application settings (JSON)
- schema://user - User schema definition
- docs://api/endpoints - API documentation
"""


# JSON resource
@resource(uri="config://app/settings", name="App Settings", mime_type="application/json")
def app_settings() -> dict:
    return {
        "app_name": "Example App",
        "version": "1.0.0",
        "debug": False,
        "features": {"analytics": True, "notifications": True, "dark_mode": False},
        "limits": {"max_requests": 1000, "timeout_seconds": 30},
    }


# Schema definition
@resource(uri="schema://user", name="User Schema", mime_type="application/json")
def user_schema() -> dict:
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": {
            "id": {"type": "integer"},
            "name": {"type": "string", "minLength": 1},
            "email": {"type": "string", "format": "email"},
            "role": {"type": "string", "enum": ["user", "admin", "moderator"]},
        },
        "required": ["id", "name", "email"],
    }


# Markdown documentation
@resource(uri="docs://api/endpoints", name="API Docs", mime_type="text/markdown")
def api_docs() -> str:
    return """# API Endpoints

## Users

### GET /users
List all users.

### GET /users/{id}
Get a specific user.

### POST /users
Create a new user.

## Settings

### GET /settings
Get application settings.

### PUT /settings
Update application settings.
"""


# Binary resource (base64 encoded in MCP)
@resource(uri="assets://logo.png", name="Logo", mime_type="image/png")
def logo() -> bytes:
    # Minimal 1x1 transparent PNG
    return bytes(
        [
            0x89,
            0x50,
            0x4E,
            0x47,
            0x0D,
            0x0A,
            0x1A,
            0x0A,
            0x00,
            0x00,
            0x00,
            0x0D,
            0x49,
            0x48,
            0x44,
            0x52,
            0x00,
            0x00,
            0x00,
            0x01,
            0x00,
            0x00,
            0x00,
            0x01,
            0x08,
            0x06,
            0x00,
            0x00,
            0x00,
            0x1F,
            0x15,
            0xC4,
            0x89,
            0x00,
            0x00,
            0x00,
            0x0A,
            0x49,
            0x44,
            0x41,
            0x54,
            0x78,
            0x9C,
            0x63,
            0x00,
            0x01,
            0x00,
            0x00,
            0x05,
            0x00,
            0x01,
            0x0D,
            0x0A,
            0x2D,
            0xB4,
            0x00,
            0x00,
            0x00,
            0x00,
            0x49,
            0x45,
            0x4E,
            0x44,
            0xAE,
            0x42,
            0x60,
            0x82,
        ]
    )


server.collect(readme, app_settings, user_schema, api_docs, logo)

if __name__ == "__main__":
    print("Static resources server: http://127.0.0.1:8000/mcp")
    print("\nResources:")
    print("  config://app/readme     - Plain text readme")
    print("  config://app/settings   - JSON configuration")
    print("  schema://user           - JSON Schema")
    print("  docs://api/endpoints    - Markdown documentation")
    print("  assets://logo.png       - Binary image")
    asyncio.run(server.serve())
