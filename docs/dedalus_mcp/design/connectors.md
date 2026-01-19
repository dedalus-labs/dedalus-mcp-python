# Connections

Declare external API dependencies. Credentials bind at runtime.

```python
from dedalus_mcp import MCPServer
from dedalus_mcp.auth import Connection, SecretKeys

github = Connection(
    name="github",
    secrets=SecretKeys(token="GITHUB_TOKEN"),
    auth_header_format="token {api_key}",
)

server = MCPServer(name="my-server", connections=[github])
```

Use in tools via `ctx.dispatch()`:

```python
@tool(description="Get GitHub user")
async def get_user() -> dict:
    ctx = get_context()
    resp = await ctx.dispatch("github", HttpRequest(method=HttpMethod.GET, path="/user"))
    return resp.response.body
```

## Connection

| Parameter            | Default              | Description                              |
| -------------------- | -------------------- | ---------------------------------------- |
| `name`               | required             | Used in `ctx.dispatch("name", ...)`      |
| `secrets`            | required             | Field names → env var names              |
| `auth_header_name`   | `"Authorization"`    | HTTP header name                         |
| `auth_header_format` | `"Bearer {api_key}"` | `{api_key}` replaced with secret value   |
| `base_url`           | `None`               | Override provider URL                    |
| `timeout_ms`         | `30000`              | 1000–300000 ms                           |

## SecretKeys

Maps field names to environment variable names:

```python
SecretKeys(token="GITHUB_TOKEN")                    # reads $GITHUB_TOKEN
SecretKeys(key="SUPABASE_KEY", url="SUPABASE_URL")  # multiple
```

For optional fields or defaults, use `Binding`:

```python
SecretKeys(
    api_key="OPENAI_API_KEY",
    org=Binding("OPENAI_ORG", optional=True),
    timeout=Binding("TIMEOUT", cast=int, default=30),
)
```

## Examples

**GitHub** — `Authorization: token xxx`

```python
Connection(name="github", secrets=SecretKeys(token="GITHUB_TOKEN"), auth_header_format="token {api_key}")
```

**Supabase** — `apikey: xxx`

```python
Connection(name="supabase", secrets=SecretKeys(key="SUPABASE_KEY"), auth_header_name="apikey", auth_header_format="{api_key}")
```

**OpenAI** — `Authorization: Bearer xxx` (default)

```python
Connection(name="openai", secrets=SecretKeys(api_key="OPENAI_API_KEY"), base_url="https://api.openai.com/v1")
```

## SecretValues (SDK side)

SDK users bind actual credentials:

```python
from dedalus_mcp.auth import SecretValues

creds = SecretValues(connection=github, token="ghp_xxxxxxxxxxxx")
```

Server code never sees raw credentials. The enclave decrypts and injects them at runtime.

## See Also

- [Authorization](authorization.md)
- [Server Manual](../manual/server.md)
