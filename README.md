# OpenMCP

Minimal, spec-faithful Python framework for building Model Context Protocol (MCP) clients and servers.

[![Y Combinator S25](https://img.shields.io/badge/Y%20Combinator-S25-orange?style=flat&logo=ycombinator&logoColor=white)](https://www.ycombinator.com/launches/Od1-dedalus-labs-build-deploy-complex-agents-in-5-lines-of-code)

OpenMCP wraps the official MCP reference SDK with ergonomic decorators, automatic schema inference, and production-grade operational features. 98% protocol compliance with MCP 2025-06-18.

## Who this is for

OpenMCP is for teams that have their infrastructure figured out. You have an IdP. You have logging. You have deployment pipelines. You don't need another framework's opinions on these things—you need MCP done correctly.

We don't bundle auth providers, CLI scaffolding, or opinionated middleware. If you want turnkey everything, FastMCP is solid. If you have your own stack and want spec-faithful MCP that integrates cleanly, you're here.

## At a glance

**137 KB.** FastMCP is 8.2 MB. 60x smaller. We ship code.

**Correct.** We track every MCP spec change at field granularity with PR citations. Zero fallback policy: you get exactly what you asked for, or an error. When the spec says a field was added in 2025-03-26, we know. When it was removed in 2025-06-18, we know. No silent misbehavior.

**Secure.** Security is a first-class concern, not an afterthought. We give you a principled auth framework that works with your existing security posture. Built for production, built for high-stakes environments.

## Why it feels different

Write functions with `@tool`, then call `server.collect(fn)`. Script-style, no context managers, no nesting. Same function, multiple servers: `server_a.collect(add)` and `server_b.collect(add)` work. No hidden state.

Runtime changes work: call `allow_tools`, `collect()` new tools, emit `notify_tools_list_changed()`, clients refresh.

Every control surface points back to a spec citation (`docs/mcp/...`) so you can check what behavior we're matching before you ship it.

Transports and services are just factories. If you don't like ours, register your own without forking the server.

Context objects are plain async helpers (`get_context().progress()`, `get_context().info()`), not opaque singletons. You can stub them in tests.

## Why OpenMCP over FastMCP

**Registration model.** FastMCP uses `@mcp.tool` where the function binds to that server at decoration time. This couples your code to a single server instance at import. Testing requires teardown. Multi-server scenarios require workarounds. OpenMCP's `@tool` decorator only attaches metadata. Registration happens when you call `server.collect(fn)`. Same function, multiple servers. No global state. Tests stay isolated. [Design rationale](docs/openmcp/ambient-registration.md).

**Protocol versioning.** MCP has multiple spec versions with real behavioral differences. OpenMCP implements the Version Profile pattern: typed `ProtocolVersion` objects, capability dataclasses per version, `current_profile()` that tells you what the client actually negotiated. FastMCP inherits from the SDK and exposes none of this. You cannot determine which protocol version your handler is serving. [Version architecture](docs/openmcp/versioning.md).

**Schema compliance.** OpenMCP validates responses against JSON schemas for each protocol version. When MCP ships breaking changes, our tests catch structural drift. FastMCP has no version-specific test infrastructure.

**Spec traceability.** Every OpenMCP feature cites its MCP spec clause in `docs/mcp/spec/`. Debugging why a client rejects your response? Trace back to the exact protocol requirement. FastMCP docs cover usage. Ours cover correctness.

**Size.** 137 KB vs 8.2 MB. We're 60x smaller. They ship docs, tests, and PNG screenshots. We ship code.

**Where FastMCP wins.** More batteries: OpenAPI integration, auth provider marketplace, CLI tooling. If you want turnkey auth with Supabase and don't want to think about it, FastMCP is probably easier to start with.

## Quickstart

### Server

```python
from openmcp import MCPServer, tool

@tool(description="Add two numbers")
def add(a: int, b: int) -> int:
    return a + b

server = MCPServer("my-server")
server.collect(add)

if __name__ == "__main__":
    import asyncio
    asyncio.run(server.serve())  # Streamable HTTP on :8000
```

### Client

```python
from openmcp import MCPClient
from openmcp.client import lambda_http_client

async def main():
    async with lambda_http_client("http://127.0.0.1:8000/mcp") as (r, w, _):
        async with MCPClient(r, w) as client:
            tools = await client.session.list_tools()
            result = await client.session.call_tool("add", {"a": 5, "b": 3})
            print(result.content)

import asyncio
asyncio.run(main())
```

## Capabilities

### Tools

```python
from typing import Literal

# Sync: pure computation, fast operations
@tool(description="Validate email")
def validate(email: str) -> bool:
    return "@" in email

# Async: I/O, network, database
@tool(description="Fetch data")
async def fetch(url: str) -> dict:
    async with httpx.AsyncClient() as client:
        return (await client.get(url)).json()

# Both work transparently
```

`tools/list`, `tools/call`, sync/async support, list change notifications, allow-lists, progress tracking. [`docs/openmcp/tools.md`](docs/openmcp/tools.md) | [`examples/hello_trip/server.py`](examples/hello_trip/server.py)

### Resources

```python
@resource("config://app/settings", mime_type="application/json")
def settings() -> dict:
    return {"theme": "dark"}

@resource_template("file://logs/{date}/{level}", mime_type="text/plain")
def logs(date: str, level: str) -> str:
    return f"Logs for {date} at {level}"

await server.notify_resource_updated("config://app/settings")  # Push to subscribers
```

Static resources, URI templates, subscriptions. [`docs/openmcp/resources.md`](docs/openmcp/resources.md)

### Prompts

```python
@prompt(name="code-review", arguments=[types.PromptArgument(name="language", required=True)])
def review(args: dict[str, str]) -> list[tuple[str, str]]:
    return [("assistant", f"You are a {args['language']} reviewer."), ("user", "Review code.")]
```

Reusable templates, typed arguments. [`docs/openmcp/prompts.md`](docs/openmcp/prompts.md)

### Completion

```python
@completion(prompt="code-review")
async def review_completions(argument, ctx) -> list[str]:
    return ["Python", "JavaScript", "Rust"] if argument.name == "language" else []
```

Argument autocompletion for prompts/resource templates. [`docs/openmcp/completions.md`](docs/openmcp/completions.md)

### Progress & Logging

```python
@tool(description="Process batch")
async def process(items: list[str]) -> dict:
    ctx = get_context()
    async with ctx.progress(total=len(items)) as tracker:
        for item in items:
            await work(item)
            await tracker.advance(1, message=f"Processed {item}")
            await ctx.info("Item done", data={"item": item})
    return {"count": len(items)}
```

Token-based progress tracking (coalesced to prevent flooding), per-session log levels. [`docs/openmcp/progress.md`](docs/openmcp/progress.md)

### Sampling

```python
async def sampling_handler(ctx, params):
    return types.CreateMessageResult(
        role="assistant",
        content=types.TextContent(type="text", text="AI response"),
        model="gpt-4"
    )

config = ClientCapabilitiesConfig(sampling=sampling_handler)
async with MCPClient(r, w, capabilities=config) as client:
    pass  # Handles sampling/createMessage from server
```

Servers request LLM completions via client. Concurrency semaphore, circuit breaker, timeouts. [`docs/openmcp/manual/client.md`](docs/openmcp/manual/client.md)

### Roots

```python
config = ClientCapabilitiesConfig(
    enable_roots=True,
    initial_roots=[types.Root(uri="file:///workspace", name="Workspace")]
)

@tool
@require_within_roots()
async def read_file(path: str) -> str:
    return Path(path).read_text()  # Path validated against roots
```

Filesystem boundaries, `RootGuard` prevents path traversal, symlink resolution. [`docs/openmcp/manual/server.md`](docs/openmcp/manual/server.md)

### Elicitation

```python
async def elicitation_handler(ctx, params):
    return types.ElicitResult(action="accept", fields={"confirm": True})

config = ClientCapabilitiesConfig(elicitation=elicitation_handler)
```

Servers request structured user input. Schema validation, timeouts, accept/decline/cancel actions. MCP 2025-06-18+. [`docs/openmcp/manual/client.md`](docs/openmcp/manual/client.md)

## Transports

**Streamable HTTP** (default): `await server.serve()` gives you `http://127.0.0.1:8000/mcp`. SSE streaming, DNS rebinding protection, origin validation, host allowlists, OAuth metadata endpoint.

**STDIO**: `await server.serve(transport="stdio")` for subprocess communication.

**Custom**: `register_transport("name", factory)` then `await server.serve(transport="name")`.

[`docs/openmcp/transports.md`](docs/openmcp/transports.md)

## Authorization

Security isn't bolted on. It's how we think about the framework.

**Session-scoped capability gating** (per-connection tool visibility):

```python
from openmcp.context import Context
from openmcp.server.dependencies import Depends

USERS = {"bob": "basic", "alice": "pro"}
SESSION_USERS: dict[str, str] = {}

def get_tier(ctx: Context) -> str:
    user_id = SESSION_USERS.get(ctx.session_id, "bob")
    return USERS[user_id]

def require_pro(tier: str) -> bool:
    return tier == "pro"

@tool(enabled=Depends(require_pro, get_tier))
async def premium_tool() -> str:
    return "Pro-only feature"
```

Dependencies re-evaluate on each request. Bob sees `[]`, Alice sees `[premium_tool]`. [`examples/tools/allow_list.py`](examples/tools/allow_list.py).

**OAuth 2.1 framework** (provider-based):

```python
class MyAuthProvider(AuthorizationProvider):
    async def validate(self, token: str) -> AuthorizationContext:
        return AuthorizationContext(subject="user-123", scopes=["read", "write"])

server = MCPServer(
    "secure-server",
    authorization=AuthorizationConfig(enabled=True, required_scopes=["read"], fail_open=False)
)
server.set_authorization_provider(MyAuthProvider())
```

RFC 9068 JWT profile, DPoP support, bearer token validation, scopes, WWW-Authenticate headers, metadata endpoint. No default provider because there's no secure default. You bring your IdP; we integrate. [`docs/openmcp/design/authorization.md`](docs/openmcp/design/authorization.md)

## Examples

[`examples/`](examples/) contains runnable demos:

- [`hello_trip/`](examples/hello_trip/) — Server + client, all basic capabilities
- [`full_demo/`](examples/full_demo/) — All capabilities, Brave Search integration
- [`progress_logging.py`](examples/progress_logging.py) — Context API, progress
- [`cancellation.py`](examples/cancellation.py) — Request cancellation
- [`advanced/feature_flag_server.py`](examples/advanced/feature_flag_server.py) — Dynamic tool registry with guardrails

Start with `hello_trip/`, then `full_demo/` for advanced patterns.

## Documentation

| Document | Description |
|----------|-------------|
| [`examples/`](examples/) | **Start here**: Runnable examples for all features |
| [`docs/openmcp/features.md`](docs/openmcp/features.md) | Complete feature matrix with compliance status |
| [`docs/openmcp/manual/server.md`](docs/openmcp/manual/server.md) | Server configuration and capability services |
| [`docs/openmcp/manual/client.md`](docs/openmcp/manual/client.md) | Client API and capability configuration |
| [`docs/openmcp/manual/security.md`](docs/openmcp/manual/security.md) | Security safeguards and authorization |
| [`docs/openmcp/versioning.md`](docs/openmcp/versioning.md) | Protocol versioning and compatibility |
| [`docs/mcp/spec/`](docs/mcp/spec/) | MCP protocol specification (receipts) |

Quick reference: [`docs/openmcp/cookbook.md`](docs/openmcp/cookbook.md) has isolated code snippets for copy-paste.

## Testing

```bash
PYTHONPATH=src uv run --python 3.12 python -m pytest
```

Covers: protocol lifecycle, registration, schema inference, subscriptions, pagination, authorization framework.

## Compliance

**MCP 2025-06-18**: 98% compliant. All mandatory features, all 9 optional capabilities (5 server, 4 client). 2% gap: authorization provider is plugin-based (framework exists, no default).

[`docs/openmcp/features.md`](docs/openmcp/features.md) has the detailed matrix.

## Design

[`CLAUDE.md`](CLAUDE.md) details:

1. **Spec-first**: Every feature cites MCP clause in `docs/mcp/spec/`
2. **Minimal surface**: Full protocol, no batteries unless performance-critical
3. **Receipt-based**: Docstrings reference spec paths
4. **Single responsibility**: One module per concern
5. **Composable**: Injected services, swappable transports
6. **SDK delegation**: Reuse reference SDK for JSON-RPC/transport
7. **Dependency discipline**: Pydantic (schemas), anyio (async), starlette/uvicorn (HTTP). Optional extras stay out of the core.

**Extend**: Add services in `src/openmcp/server/services/`, transports via `register_transport()`, auth via `AuthorizationProvider`.

## License

MIT
