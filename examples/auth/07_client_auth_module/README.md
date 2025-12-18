# Client Auth Module Examples

This directory demonstrates the new `dedalus_mcp.client.auth` module for spec-compliant OAuth authentication.

## Overview

The auth module provides:

- **`ClientCredentialsAuth`**: M2M / backend service authentication
- **`TokenExchangeAuth`**: User delegation via token exchange (RFC 8693)
- **`DeviceCodeAuth`**: CLI tool authentication (stub)
- **`AuthorizationCodeAuth`**: Browser-based authentication (stub, planned for Clerk)

## Quick Start

```bash
# Set the M2M secret
export MCP_CLIENT_SECRET="your-m2m-secret"

# Run the example
uv run python examples/auth/07_client_auth_module/client_credentials_example.py
```

## Usage with MCPClient

```python
from dedalus_mcp.client import MCPClient
from dedalus_mcp.client.auth import ClientCredentialsAuth

# Option 1: Auto-discovery from protected resource
auth = await ClientCredentialsAuth.from_resource(
    resource_url="https://mcp.example.com/mcp",
    client_id="m2m",
    client_secret=os.environ["M2M_SECRET"],
)
await auth.get_token()
client = await MCPClient.connect("https://mcp.example.com/mcp", auth=auth)

# Option 2: Direct construction (when you know the AS)
from dedalus_mcp.client.auth import fetch_authorization_server_metadata

async with httpx.AsyncClient() as http:
    server_metadata = await fetch_authorization_server_metadata(http, "https://as.example.com")

auth = ClientCredentialsAuth(
    server_metadata=server_metadata,
    client_id="m2m",
    client_secret=secret,
)
await auth.get_token()
client = await MCPClient.connect("https://mcp.example.com/mcp", auth=auth)
```

## Token Exchange (User Delegation)

```python
from dedalus_mcp.client.auth import TokenExchangeAuth

# Exchange a Clerk/Auth0 token for an MCP-scoped token
auth = await TokenExchangeAuth.from_resource(
    resource_url="https://mcp.example.com/mcp",
    client_id="dedalus-sdk",
    subject_token=clerk_session_token,
)
await auth.get_token()
client = await MCPClient.connect("https://mcp.example.com/mcp", auth=auth)
```

## Architecture

The module implements:

- **RFC 9728**: OAuth 2.0 Protected Resource Metadata discovery
- **RFC 8414**: OAuth 2.0 Authorization Server Metadata discovery
- **RFC 6749 Section 4.4**: Client Credentials Grant
- **RFC 8693**: Token Exchange Grant
- **RFC 8707**: Resource Indicators
