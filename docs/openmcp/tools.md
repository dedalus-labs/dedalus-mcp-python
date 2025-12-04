# Tools

**Problem**: MCP tools must appear in `tools/list`, report JSON Schemas, accept allow-list gating, and surface JSON-RPC errors consistently. Re-implementing this logic for each project is error prone.

**Solution**: Use decorators or ambient registries that turn plain Python callables into MCP tool descriptors, automatically handling schema generation, capability advertisement, and JSON-RPC plumbing.

**Dedalus MCP**: Decorate any callable with `@tool` inside `server.binding()`. Dedalus MCP builds the input schema from type hints, wires the handler into the reference SDK, and exposes it both as a Python attribute and via `tools/call`. Pagination for `tools/list` obeys the standard cursor semantics (`docs/mcp/capabilities/pagination`): clients pass the opaque `cursor` token received in `nextCursor`, malformed cursors raise `INVALID_PARAMS`, and a missing `nextCursor` means the surface is exhausted. Allow-lists (`server.allow_tools(...)`) and `enabled` predicates give you fine-grained runtime control. The decorator accepts richer metadata—`title`, `annotations`, `output_schema`, and `icons`—which are surfaced through `types.Tool` / `ToolAnnotations` exactly as the spec describes.

```python
from dedalus_mcp import MCPServer, get_context, tool

server = MCPServer("calc")

with server.binding():
    @tool(description="Human-friendly addition")
    async def add(a: int, b: int) -> int:
        ctx = get_context()
        await ctx.debug("adding", data={"a": a, "b": b})
        return a + b

    @tool(description="Uppercase text", enabled=lambda srv: srv.tool_names)
    def shout(text: str) -> str:
        return text.upper()

# Restrict exposed surface if needed
server.allow_tools(["add"])  # shout stays registered but hidden
```

### Dependency injection & session-scoped authorization

`Depends()` enables FastAPI-style dependency injection for runtime capability gating, business rules (plan tiers, feature flags), and request-scoped state injection:

```python
from dedalus_mcp import MCPServer, tool
from dedalus_mcp.context import Context
from dedalus_mcp.server.dependencies import Depends

server = MCPServer("plans")
USERS = {"bob": "basic", "alice": "pro"}
SESSION_USERS: dict[str, str] = {}  # Maps MCP session ID -> user ID


def get_tier(ctx: Context) -> str:
    """Extract user tier from session-scoped storage."""
    session_id = ctx.session_id
    user_id = SESSION_USERS.get(session_id, "bob")
    return USERS[user_id]


def require_pro(tier: str) -> bool:
    return tier == "pro"


with server.binding():

    @tool(description="Premium forecast", enabled=Depends(require_pro, get_tier))
    async def premium(days: int = 7) -> dict[str, str | int]:
        return {"plan": "pro", "days": days}
```

**Auto-injection**: Parameters typed as `Context` are automatically injected—no need for `Depends(get_context)`. The framework inspects type hints and supplies the current request context at resolution time.

**Session-scoped authorization**: Store user identity keyed by `ctx.session_id` (unique per MCP client connection). Each `tools/list` or `tools/call` request re-evaluates `enabled` predicates with fresh dependency resolution, so you can gate capabilities per authenticated session. See the MCP session lifecycle in `docs/mcp/core/lifecycle/lifecycle-phases.md`.

**Import patterns**: Core exports (`MCPServer`, `tool`, `get_context`) live in `dedalus_mcp.__init__.py`; advanced features like `Depends` are in submodules (`dedalus_mcp.server.dependencies`).

**Full example**: [`examples/tools/allow_list.py`](../../examples/tools/allow_list.py) demonstrates session-scoped authorization with two users ("bob"/"alice") where `premium_tool` only appears in alice's `tools/list` response.

- Spec receipts: `docs/mcp/spec/schema-reference/tools-list.md`, `tools-call.md`
- Input schema inference leans on `pydantic.TypeAdapter`; unsupported annotations fall back to permissive schemas.
- Return annotations automatically generate `outputSchema` metadata (non-object outputs are wrapped as `{ "result": ... }`) and the runtime normalizer produces matching `structuredContent` so clients can consume structured results directly.
- For list change notifications, toggle `NotificationFlags.tools_changed` and emit updates when your registry mutates.
- `Depends()` supports nested dependencies, cycle detection (raises `CircularDependencyError`), and per-request caching via `Context`. Dependencies are resolved once per MCP request and cached for reuse within that request scope.
