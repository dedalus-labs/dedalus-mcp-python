# Dedalus MCP Overview

Dedalus MCP is a thin, spec-faithful wrapper over the Model Context Protocol (MCP) reference SDK. It
adds light ergonomics—ambient registration, schema inference, simplified transports—while keeping the
wire behavior identical to the MCP specification.

## Architectural Layers

```
┌────────────────────────────────────────────────────────────┐
│ Application code (tools, resources, prompts, examples)     │
├────────────────────────────────────────────────────────────┤
│ Dedalus MCP convenience layer                                  │
│  • MCPServer / MCPClient                                   │
│  • Capability services (tools/resources/prompts/…)         │
│  • Context helpers (logging/progress/authorization)        │
│  • Transport adapters (STDIO, Streamable HTTP)             │
├────────────────────────────────────────────────────────────┤
│ MCP reference SDK (mcp.server, mcp.client, mcp.types)      │
├────────────────────────────────────────────────────────────┤
│ Runtime (asyncio/anyio, Starlette/Uvicorn, OS transport)   │
└────────────────────────────────────────────────────────────┘
```

The reference SDK handles protocol lifecycle (initialize -> initialized -> normal operation) and JSON-RPC
plumbing. Dedalus MCP layers on:

- **Registration ergonomics** – decorators and `binding()` scopes to declare capabilities.
- **Schema handling** – `pydantic` powered inference plus normalization adapters.
- **Operational glue** – pagination helpers, heartbeat service, subscription bookkeeping.
- **Opt-in security hooks** – transport security defaults, authorization scaffolding.

## Lifecycle Snapshot

1. **Initialization**: `MCPClient` sends `initialize`, negotiating protocol version and capabilities.
2. **Operation**: Client issues `tools/list`, `resources/read`, etc.; server services dispatch to
   registered handlers, log/progress helpers use `get_context()`.
3. **Shutdown**: Transport closes (STDIO exit, HTTP connection close). The SDK cleans up session state.

All Dedalus MCP services respect the MCP spec receipts listed in `docs/mcp/core/` and `docs/mcp/capabilities/`.
When the framework offers optional behavior (e.g., list-change notifications, subscriptions), the
configuration defaults mirror the spec’s SHOULD/SHOULD NOT guidance.

## Capabilities at a Glance

| Capability     | Implementation                                                | Key docs                        |
| -------------- | ------------------------------------------------------------- | ------------------------------- |
| Tools          | `src/dedalus_mcp/server/services/tools.py`                        | `docs/dedalus_mcp/manual/server.md` |
| Resources      | `src/dedalus_mcp/server/services/resources.py`                    | `docs/dedalus_mcp/manual/server.md` |
| Prompts        | `src/dedalus_mcp/server/services/prompts.py`                      | `docs/dedalus_mcp/manual/server.md` |
| Completions    | `src/dedalus_mcp/server/services/completions.py`                  | `docs/dedalus_mcp/manual/server.md` |
| Sampling       | `src/dedalus_mcp/server/services/sampling.py`                     | `docs/dedalus_mcp/manual/server.md` |
| Elicitation    | `src/dedalus_mcp/server/services/elicitation.py`                  | `docs/dedalus_mcp/manual/server.md` |
| Logging        | `src/dedalus_mcp/server/services/logging.py`, `get_context()`     | `docs/dedalus_mcp/manual/server.md` |
| Progress       | `src/dedalus_mcp/progress.py`, `get_context().progress()`         | `docs/dedalus_mcp/manual/server.md` |
| Authorization  | `src/dedalus_mcp/server/authorization.py` (opt-in scaffolding)    | `docs/dedalus_mcp/manual/security.md` |
| Transports     | `src/dedalus_mcp/server/transports/*`, `src/dedalus_mcp/client/transports.py` | `docs/dedalus_mcp/manual/server.md` |

The following sections dive into server behavior, client behavior, configuration, operational
security, and a gallery of end-to-end examples.
