# Dedalus MCP

Minimal, spec-faithful Python framework for building Model Context Protocol (MCP) clients and servers.

[![Y Combinator S25](https://img.shields.io/badge/Y%20Combinator-S25-orange?style=flat&logo=ycombinator&logoColor=white)](https://www.ycombinator.com/launches/Od1-dedalus-labs-build-deploy-complex-agents-in-5-lines-of-code)

Dedalus MCP wraps the official MCP reference SDK with ergonomic decorators, automatic schema inference, and production-grade operational features. Full compliance with MCP.

## Who this is for

Dedalus MCP is for teams that have their infrastructure figured out. You have an IdP. You have logging. You have deployment pipelines. You don't need another framework's opinions on these things—you need MCP done correctly.

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

## Why Dedalus MCP over FastMCP

**Registration model.** FastMCP uses `@mcp.tool` where the function binds to that server at decoration time. This couples your code to a single server instance at import. Testing requires teardown. Multi-server scenarios require workarounds. Dedalus MCP's `@tool` decorator only attaches metadata. Registration happens when you call `server.collect(fn)`. Same function, multiple servers. No global state. Tests stay isolated. [Design rationale](docs/dedalus_mcp/ambient-registration.md).

**Protocol versioning.** MCP has multiple spec versions with real behavioral differences. Dedalus MCP implements the Version Profile pattern: typed `ProtocolVersion` objects, capability dataclasses per version, `current_profile()` that tells you what the client actually negotiated. FastMCP inherits from the SDK and exposes none of this. You cannot determine which protocol version your handler is serving. [Version architecture](docs/dedalus_mcp/versioning.md).

**Schema compliance.** Dedalus MCP validates responses against JSON schemas for each protocol version. When MCP ships breaking changes, our tests catch structural drift. FastMCP has no version-specific test infrastructure.

**Spec traceability.** Every Dedalus MCP feature cites its MCP spec clause in `docs/mcp/spec/`. Debugging why a client rejects your response? Trace back to the exact protocol requirement. FastMCP docs cover usage. Ours cover correctness.

**Size.** 137 KB vs 8.2 MB. We're 60x smaller. They ship docs, tests, and PNG screenshots. We ship code.

**Client ergonomics.** `client = await MCPClient.connect(url)` returns a ready-to-use client. No nested context managers required. Explicit `close()` or optional `async with` for cleanup. `weakref.finalize()` safety net warns if you forget. FastMCP requires `async with mcp.run_client():` context manager nesting.

**Where FastMCP wins.** More batteries: OpenAPI integration, auth provider marketplace, CLI tooling. If you want turnkey auth with Supabase and don't want to think about it, FastMCP is probably easier to start with.

## Quickstart

### Server

```python
from dedalus_mcp import MCPServer, tool

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
from dedalus_mcp.client import MCPClient

async def main():
    client = await MCPClient.connect("http://127.0.0.1:8000/mcp")
    tools = await client.list_tools()
    result = await client.call_tool("add", {"a": 5, "b": 3})
    print(result)
    await client.close()

import asyncio
asyncio.run(main())
```

For protected servers using DPoP (RFC 9449):

```python
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.backends import default_backend
from dedalus_mcp.client import MCPClient, DPoPAuth

# Your DPoP key (same key used when obtaining the token)
dpop_key = ec.generate_private_key(ec.SECP256R1(), default_backend())

auth = DPoPAuth(access_token="eyJ...", dpop_key=dpop_key)
client = await MCPClient.connect("https://mcp.example.com/mcp", auth=auth)
```

<!-- ## Capabilities

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

`tools/list`, `tools/call`, sync/async support, list change notifications, allow-lists, progress tracking. [`docs/dedalus_mcp/tools.md`](docs/dedalus_mcp/tools.md) | [`examples/hello_trip/server.py`](examples/hello_trip/server.py)

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

Static resources, URI templates, subscriptions. [`docs/dedalus_mcp/resources.md`](docs/dedalus_mcp/resources.md)

### Prompts

```python
@prompt(name="code-review", arguments=[types.PromptArgument(name="language", required=True)])
def review(args: dict[str, str]) -> list[tuple[str, str]]:
    return [("assistant", f"You are a {args['language']} reviewer."), ("user", "Review code.")]
```

Reusable templates, typed arguments. [`docs/dedalus_mcp/prompts.md`](docs/dedalus_mcp/prompts.md)

### Completion

```python
@completion(prompt="code-review")
async def review_completions(argument, ctx) -> list[str]:
    return ["Python", "JavaScript", "Rust"] if argument.name == "language" else []
```

Argument autocompletion for prompts/resource templates. [`docs/dedalus_mcp/completions.md`](docs/dedalus_mcp/completions.md)

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

Token-based progress tracking (coalesced to prevent flooding), per-session log levels. [`docs/dedalus_mcp/progress.md`](docs/dedalus_mcp/progress.md)

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

Servers request LLM completions via client. Concurrency semaphore, circuit breaker, timeouts. [`docs/dedalus_mcp/manual/client.md`](docs/dedalus_mcp/manual/client.md)

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

Filesystem boundaries, `RootGuard` prevents path traversal, symlink resolution. [`docs/dedalus_mcp/manual/server.md`](docs/dedalus_mcp/manual/server.md)

### Elicitation

```python
async def elicitation_handler(ctx, params):
    return types.ElicitResult(action="accept", fields={"confirm": True})

config = ClientCapabilitiesConfig(elicitation=elicitation_handler)
```

Servers request structured user input. Schema validation, timeouts, accept/decline/cancel actions. MCP 2025-06-18+. [`docs/dedalus_mcp/manual/client.md`](docs/dedalus_mcp/manual/client.md)

## Transports

**Streamable HTTP** (default): `await server.serve()` gives you `http://127.0.0.1:8000/mcp`. SSE streaming, DNS rebinding protection, origin validation, host allowlists, OAuth metadata endpoint.

**STDIO**: `await server.serve(transport="stdio")` for subprocess communication.

**Custom**: `register_transport("name", factory)` then `await server.serve(transport="name")`.

[`docs/dedalus_mcp/transports.md`](docs/dedalus_mcp/transports.md) -->

<!-- ## Authorization

[4 tools called]

Let me read these large files in chunks:

[4 tools called]

Let me continue reading the remaining content:

[2 tools called]

I've now read through all the auth specification documents. Let me synthesize my understanding:

---

**The Core Architecture:**

You've designed a **dual-layer zero-trust model** that solves the critical gap in MCP auth: most downstream APIs (OpenAI, databases, SaaS) aren't OAuth apps, yet you need to call them securely on behalf of users without exposing credentials to untrusted third-party marketplace servers.

**Layer 1 — MCP Authorization:** Standard OAuth 2.1. The Dedalus AS issues short-lived, audience-bound tokens that say "this client can invoke this MCP server." Tokens carry `org_id`, `connection_ids`, scopes. PKCE mandatory, DPoP for sender-constraining, RFC 9728 Protected Resource Metadata for discovery.

**Layer 2 — Credential Authorization (The Enclave):** This is your differentiation. The Dedalus Enclave is a signer/vault service running in Nitro Enclaves that:
- Holds encrypted downstream credentials (API keys, DB passwords, OAuth refresh tokens)
- Exposes exactly one capability: `dispatch(intent_name, args)`
- Validates intents against a contract, decrypts credentials in isolated memory, calls the downstream, and returns only results—never credentials

**The `dispatch()` Pattern:**

User code runs in untrusted compute (Lambda, Fargate, EC2). It can do arbitrary NumPy, loops, preprocessing—but it can **only** reach downstream providers through `dispatch()`. This is the "syscall" boundary. The enclave is the kernel; user code is userspace.

```python
# User code never sees API keys
result = await dispatch("query_database", {"table": "users", "limit": 100})
```

**Two Credential Models:**

1. **Organization-owned (Connection Handles):** Pre-registered in DynamoDB, keyed by `(org_id, connection_id)`. Server-side custody in vault. The `ddls:connections` JWT claim authorizes access.

2. **User-owned (User Delegation):** Client-side custody in OS keychain. SDK encrypts with Enclave's public key. Marketplace servers receive opaque ciphertext and must forward to Enclave for execution. `ddls:user_delegations` claim tracks these.

**Open-Source vs Proprietary Split:**

The Dedalus MCP SDK (open-source) defines `DispatchBackend` as an abstract interface. OSS users can run in "direct mode" with env var credentials (no zero-trust guarantees) or bring their own vault.

**Marketplace Isolation:**

Third-party MCP servers can orchestrate business logic but cannot access plaintext credentials. Even if compromised, they only see encrypted blobs. The Enclave is the single point where decryption happens, and it's not user-accessible. -->

<!-- ---

**Questions / Ambiguities I noticed:**

1. The docs mention both `contract` and `intents_manifest` in connection records—these seem synonymous. Should we pick one term?

2. Section 5.4 (User Delegation) describes device-specific key derivation via HKDF, but the wire format shows `kid: "dedalus-enclave-key-v3"` which implies Enclave public key. The flow needs to be crisp: is the user token encrypted with a device-derived key (stored in keychain) or the Enclave's RSA public key?

3. The `DispatchBackend` interface in the revisions-convo shows `HttpDispatchBackend` talking to a Dispatch Gateway that fans out to signer nodes. But auth-specs-notion Section 5.6 shows RS calling Enclave directly via VPC endpoint. Need to clarify if there's a gateway layer or direct RS→Enclave.


**Session-scoped capability gating** (per-connection tool visibility):

```python
from dedalus_mcp.context import Context
from dedalus_mcp.server.dependencies import Depends

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

RFC 9068 JWT profile, DPoP support, bearer token validation, scopes, WWW-Authenticate headers, metadata endpoint. No default provider because there's no secure default. You bring your IdP; we integrate. [`docs/dedalus_mcp/design/authorization.md`](docs/dedalus_mcp/design/authorization.md)

### Typed Connectors (Advanced)

For database drivers, SDK clients, or vault-based credential management:

```python
from dedalus_mcp.server.connectors import define, EnvironmentCredentialLoader, EnvironmentCredentials, Credentials

# Define typed schema
PostgresConn = define(
    kind="postgres",
    params={"host": str, "port": int, "database": str},
    auth=["password"],
)

# Map environment variables
loader = EnvironmentCredentialLoader(
    connector=PostgresConn,
    variants={
        "password": EnvironmentCredentials(
            config=Credentials(host="POSTGRES_HOST", port="POSTGRES_PORT", database="POSTGRES_DB"),
            secrets=Credentials(username="POSTGRES_USER", password="POSTGRES_PASSWORD"),
        ),
    },
)

# Load and validate (returns typed Pydantic models)
resolved = loader.load("password")
# resolved.config.host: str, resolved.config.port: int (auto-cast)
# resolved.auth.username: str, resolved.auth.password: str
```

Provides compile-time type safety and runtime validation. Use `Connection` for simple HTTP APIs; use `define()` when you need typed models or driver integration. [`examples/advanced/typed_connectors.py`](examples/advanced/typed_connectors.py)

## Examples

[`examples/`](examples/) contains runnable demos:

- [`hello_trip/`](examples/hello_trip/) — Server + client, all basic capabilities
- [`full_demo/`](examples/full_demo/) — All capabilities, Brave Search integration
- [`progress_logging.py`](examples/progress_logging.py) — Context API, progress
- [`cancellation.py`](examples/cancellation.py) — Request cancellation
- [`advanced/feature_flag_server.py`](examples/advanced/feature_flag_server.py) — Dynamic tool registry with guardrails
- [`advanced/typed_connectors.py`](examples/advanced/typed_connectors.py) — Typed connector pattern with define()

Start with `hello_trip/`, then `full_demo/` for advanced patterns.

## Documentation

| Document | Description |
|----------|-------------|
| [`examples/`](examples/) | **Start here**: Runnable examples for all features |
| [`docs/dedalus_mcp/features.md`](docs/dedalus_mcp/features.md) | Complete feature matrix with compliance status |
| [`docs/dedalus_mcp/manual/server.md`](docs/dedalus_mcp/manual/server.md) | Server configuration and capability services |
| [`docs/dedalus_mcp/manual/client.md`](docs/dedalus_mcp/manual/client.md) | Client API and capability configuration |
| [`docs/dedalus_mcp/manual/security.md`](docs/dedalus_mcp/manual/security.md) | Security safeguards and authorization |
| [`docs/dedalus_mcp/versioning.md`](docs/dedalus_mcp/versioning.md) | Protocol versioning and compatibility |
| [`docs/mcp/spec/`](docs/mcp/spec/) | MCP protocol specification (receipts) |

Quick reference: [`docs/dedalus_mcp/cookbook.md`](docs/dedalus_mcp/cookbook.md) has isolated code snippets for copy-paste.

## Testing

```bash
PYTHONPATH=src uv run --python 3.12 python -m pytest
```

Covers: protocol lifecycle, registration, schema inference, subscriptions, pagination, authorization framework.

## Compliance

**MCP 2025-06-18**: 98% compliant. All mandatory features, all 9 optional capabilities (5 server, 4 client). 2% gap: authorization provider is plugin-based (framework exists, no default).

[`docs/dedalus_mcp/features.md`](docs/dedalus_mcp/features.md) has the detailed matrix.

## Design

[`CLAUDE.md`](CLAUDE.md) details:

1. **Spec-first**: Every feature cites MCP clause in `docs/mcp/spec/`
2. **Minimal surface**: Full protocol, no batteries unless performance-critical
3. **Receipt-based**: Docstrings reference spec paths
4. **Single responsibility**: One module per concern
5. **Composable**: Injected services, swappable transports
6. **SDK delegation**: Reuse reference SDK for JSON-RPC/transport
7. **Dependency discipline**: Pydantic (schemas), anyio (async), starlette/uvicorn (HTTP). Optional extras stay out of the core.

**Extend**: Add services in `src/dedalus_mcp/server/services/`, transports via `register_transport()`, auth via `AuthorizationProvider`. -->

## License

MIT
