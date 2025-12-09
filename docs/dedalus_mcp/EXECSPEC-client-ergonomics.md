# EXECSPEC: Client Ergonomics Refactor — **COMPLETE**

## Goal

Provide script-friendly async client without mandatory context managers, while maintaining correctness guarantees.

**Primary API:**
```python
client = await MCPClient.connect("http://localhost:8000/mcp")
tools = await client.list_tools()
await client.close()
```

**Optional context manager:**
```python
async with MCPClient.connect("http://localhost:8000/mcp") as client:
    tools = await client.list_tools()
```

## Design Principles

1. **Async is unavoidable** — MCP's bidirectional protocol (server can request sampling, elicitation) requires async for full functionality.

2. **Factory method over constructor** — `connect()` returns an already-connected client, matching Stainless ergonomics.

3. **Explicit cleanup** — `close()` method for deterministic cleanup in script-style code.

4. **Context manager as convenience** — `async with` works but isn't required.

5. **Finalizer as safety net** — `weakref.finalize()` logs warnings and attempts cleanup if user forgets `close()`.

## Architecture

```
MCPClient
├── connect(url, ...) -> MCPClient        # Factory, returns connected client
├── close() -> None                        # Explicit cleanup
├── __aenter__ / __aexit__                 # Optional context manager
├── _finalizer: weakref.finalize           # Safety net for forgotten close()
├── _closed: bool                          # Prevent double-close
└── session: ClientSession                 # Underlying MCP session
```

## Invariants

### Phase 1: Core Lifecycle — **VERIFIED**
- [x] `connect()` returns an already-initialized client
- [x] `close()` cleans up resources and is idempotent
- [x] Accessing `session` after `close()` raises `RuntimeError`
- [x] Double `close()` is safe (no-op)
- [x] `_finalizer` logs warning if `close()` wasn't called

### Phase 2: Context Manager Support — **VERIFIED**
- [x] `async with MCPClient.connect(...)` works as expected
- [x] Exiting context manager calls `close()` automatically
- [x] Context manager re-entry on closed client raises

### Phase 3: Integration with Transports — **VERIFIED**
- [x] `connect()` works with streamable-http transport
- [x] Context manager closes properly with real transport
- [x] Unknown transport raises `ValueError`

### Phase 4: Operations on Connected Client — **VERIFIED**
- [x] All operations raise `RuntimeError` after `close()`

## Progress

Phase 1: Core Lifecycle — **COMPLETE**
- [x] Test: `test_connect_returns_initialized_client`
- [x] Test: `test_close_is_idempotent`
- [x] Test: `test_session_after_close_raises`
- [x] Test: `test_finalizer_warns_on_unclosed`
- [x] Implementation: Refactor `MCPClient.connect()`

Phase 2: Context Manager Support — **COMPLETE**
- [x] Test: `test_context_manager_closes_on_exit`
- [x] Test: `test_context_manager_closes_on_exception`
- [x] Test: `test_reentry_on_closed_raises`
- [x] Implementation: Update `__aenter__` / `__aexit__`

Phase 3: Transport Integration — **COMPLETE**
- [x] Test: `test_mcpclient_connect_streamable_http`
- [x] Test: `test_mcpclient_connect_context_manager`
- [x] Test: `test_mcpclient_connect_unknown_transport`
- [x] Implementation: Adapt transport helpers (done in connect())

Phase 4: Operations — **COMPLETE**
- [x] Test: `test_operations_raise_when_closed`

## Files to Modify

- `src/dedalus_mcp/client/core.py` — Main refactor
- `src/dedalus_mcp/client/connection.py` — May merge into core or deprecate
- `src/dedalus_mcp/client/__init__.py` — Update exports
- `tests/test_client_ergonomics.py` — New test file

## Non-Goals

- Sync client wrapper (MCP is fundamentally async)
- Reference counting / reentrancy (keep simple; users can create new clients)
- Connection pooling (out of scope)

## References

- Stainless SDK: `__del__` cleanup, optional context manager
- Speakeasy SDK: `weakref.finalize()`, more robust async cleanup
- FastMCP Client: Required context manager, reference counting for reentrancy
- anyio: `aclose_forcefully()` for cancelled-scope cleanup

