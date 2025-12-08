# Connector Framework

This document describes the connector and credential binding framework used to securely configure MCP servers with external service credentials.

## Overview

The connector framework provides a declarative way to:

1. Define connection types with typed parameters and auth methods
2. Bind environment variables to credentials at runtime
3. Serialize server configuration for SDK transport

## Core Components

### ConnectorDefinition

Declares a connection type with required parameters and supported auth methods:

```python
from dedalus_mcp.server.connectors import define

OpenAIConn = define(
    kind="openai",
    params={"model": str, "base_url": str},
    auth=["api_key", "azure_ad"],
    description="OpenAI API connection"
)
```

### EnvironmentBindings

Maps credential fields to environment variable names. Accepts unlimited kwargs:

```python
from dedalus_mcp.server.connectors import EnvironmentBindings, EnvironmentBinding

bindings = EnvironmentBindings(
    api_key="OPENAI_API_KEY",
    org_id=EnvironmentBinding("OPENAI_ORG_ID", optional=True),
    base_url=EnvironmentBinding("OPENAI_BASE_URL", default="https://api.openai.com/v1"),
)
```

Each entry is either:
- A string (shorthand for `EnvironmentBinding(name)`)
- An `EnvironmentBinding` with options: `name`, `cast`, `default`, `optional`

### EnvironmentCredentials

Groups config and secret bindings for an auth method:

```python
from dedalus_mcp.server.connectors import EnvironmentCredentials, EnvironmentBindings

api_key_auth = EnvironmentCredentials(
    config=EnvironmentBindings(
        base_url="OPENAI_BASE_URL",
    ),
    secrets=EnvironmentBindings(
        api_key="OPENAI_API_KEY",
    ),
)
```

### EnvironmentCredentialLoader

Loads credentials from environment for a connector type:

```python
from dedalus_mcp.server.connectors import EnvironmentCredentialLoader

loader = EnvironmentCredentialLoader(
    connector=OpenAIConn,
    variants={
        "api_key": EnvironmentCredentials(
            config=EnvironmentBindings(base_url="OPENAI_BASE_URL"),
            secrets=EnvironmentBindings(api_key="OPENAI_API_KEY"),
        ),
    },
)

# Load at runtime
resolved = loader.load("api_key")
# resolved.handle -> ConnectorHandle
# resolved.config -> typed Pydantic model
# resolved.auth -> typed Pydantic model with secrets
```

## MCPServer Integration

When configuring an MCP server for SDK transport:

```python
from dedalus_mcp import MCPServer
from dedalus_mcp.server.connectors import EnvironmentBindings

server = MCPServer(
    name="openai-chat",
    env=EnvironmentBindings(
        api_key="OPENAI_API_KEY",
        org_id="OPENAI_ORG_ID",
    ),
)
```

The `env` parameter defines how credentials map to environment variables when the server runs in the enclave.

## SDK Serialization

When the Dedalus SDK initializes with MCP servers, it:

1. Reads `server.env.entries` to get credential bindings
2. Matches credential names to `secrets` dict passed to SDK
3. Builds connection record with encrypted credentials + env bindings

```python
from dedalus import Dedalus
from dedalus_mcp import MCPServer
from dedalus_mcp.server.connectors import EnvironmentBindings

server = MCPServer(
    name="chat",
    env=EnvironmentBindings(api_key="OPENAI_API_KEY"),
)

client = Dedalus(
    api_key="dsk-...",
    secrets={"openai": {"api_key": "sk-..."}},
    mcp_servers=[server],
)
```

The SDK serializes:

```json
{
  "handle": "ddls:conn:uuid7",
  "encrypted_credentials": "...",
  "env_bindings": {
    "api_key": "OPENAI_API_KEY"
  }
}
```

**Note:** MCP server capabilities (tools, prompts, resources) are *not* stored with the connection. They are discovered at runtime via the MCP protocol (`tools/list`, `prompts/list`, `resources/list`). The connection stores only credentials and how to inject them.

At dispatch time, the enclave:

1. Decrypts credentials
2. Injects values into env vars per `env_bindings`
3. Connects to MCP server, discovers available tools/prompts/resources
4. MCP server code reads `os.environ["OPENAI_API_KEY"]`

## Serialization Protocol

For SDK transport, the **stored payload** contains only credential bindings:

| Field | Source | Description |
|-------|--------|-------------|
| `name` | `server.name` | Server identifier |
| `env_bindings` | `server.env.entries` | Credential → env var mapping |

For local introspection (debugging, validation), servers can also expose:

| Field | Source | Description |
|-------|--------|-------------|
| `tools` | `server.tools._tool_specs` | Tool definitions (runtime-discovered) |
| `prompts` | `server.prompts._prompt_specs` | Prompt definitions (runtime-discovered) |
| `resources` | `server.resources._resource_specs` | Resource definitions (runtime-discovered) |

### to_dict() Method

Servers should implement serialization for introspection:

```python
def to_dict(self) -> dict:
    return {
        "name": self.name,
        "env_bindings": {
            name: binding.name
            for name, binding in self.env.entries.items()
        } if self.env else {},
        # Tools included for local introspection only, not stored
        "tools": [
            {"name": name, "description": spec.description, "schema": spec.input_schema}
            for name, spec in self.tools._tool_specs.items()
        ],
    }
```

## Security Considerations

1. **Secrets never in server code**: Server defines env var names, not values
2. **Enclave injection**: Credentials injected at runtime by trusted enclave
3. **Binding validation**: `EnvironmentCredentialLoader` validates bindings match connector definition
4. **Type safety**: Pydantic models enforce credential structure

## See Also

- [Authorization Design](authorization.md) - OAuth 2.1 token flow
- [Server Manual](../manual/server.md) - Server configuration
- `src/dedalus_mcp/server/connectors.py` - Implementation
