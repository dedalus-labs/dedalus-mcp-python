# EXECSPEC: Examples & Documentation Polish

**STATUS: COMPLETE**

## Goal

Create runnable, tested examples that demonstrate Dedalus MCP's capabilities. Fix existing examples. Document the expository style.

## Deliverables

### Phase 1: Style Documentation ✓
- [x] Added `expository-patterns.mdx` to dedalus_docs/src/writing
- [x] Documented Problem/Solution/Dedalus MCP pattern

### Phase 2: Client Examples ✓
- [x] `showcase/01_client.py` — Script-style MCPClient.connect()
- [x] `client/basic_connect.py` — Standalone basic client
- [x] `client/dpop_auth.py` — RFC 9449 DPoP authentication
- [x] `client/bearer_auth.py` — Simple Bearer token auth
- [x] Added convenience methods to MCPClient: `list_tools()`, `call_tool()`, `list_resources()`, `read_resource()`, `list_prompts()`, `get_prompt()`

### Phase 3: Server Examples ✓
- [x] `showcase/01_minimal.py` — Minimal 15-line server
- [x] `showcase/02_bidirectional_server.py` — Server requesting LLM from client
- [x] `showcase/03_realtime_server.py` — Hot-reload tools via control API
- [x] `showcase/04_live_resources_server.py` — Live-updating resources
- [x] `showcase/05_progress_server.py` — Progress reporting

### Phase 4: Integration Examples ✓
- [x] `showcase/run_all.sh` — Integration test script
- [x] All showcase examples tested and passing

### Phase 5: Dynamic Server (Bidirectional Features) ✓
- [x] Fixed `showcase/03_realtime_server.py` — HTTP control API on :8001
- [x] Tested: add tool, list tools, call tool, remove tool
- [x] `notify_tools_list_changed()` notifies connected clients
- [x] Documented ContextVar-powered real-time updates

## Test Results

```
=========================================
Dedalus MCP Showcase Integration Tests
=========================================

[01] Testing minimal server + client...
Connected to: minimal
Available tools: ['add']
add(40, 2) = 42
[01] ✓ Minimal test passed

[02] Testing bidirectional (sampling)...
Connected to: bidirectional
Result: {'text': '...', 'sentiment': 'positive', 'model': 'mock-llm-1.0'}
[02] ✓ Bidirectional test passed

[03] Testing real-time tool updates...
Connected to: realtime
Initial tools: ['health', 'server_time']
Tools after add: ['health', 'server_time', 'calculator']
calculator result: {'tool': 'calculator', 'args': {...}, 'dynamic': True}
Tools after remove: ['health', 'server_time', 'translate']
[03] ✓ Real-time test passed

=========================================
All showcase tests passed!
=========================================
```

## Files Changed

- `/Users/nguyen/Desktop/dedalus-labs/codebase/dedalus_docs/src/writing/expository-patterns.mdx` — Style guide
- `/Users/nguyen/Desktop/dedalus-labs/codebase/dedalus_mcp/examples/showcase/` — New showcase directory
- `/Users/nguyen/Desktop/dedalus-labs/codebase/dedalus_mcp/src/dedalus_mcp/client/core.py` — Added convenience methods
- `/Users/nguyen/Desktop/dedalus-labs/codebase/dedalus_mcp/examples/dynamic_server.py` — Updated to use new patterns
