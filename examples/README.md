# Dedalus MCP Examples

Runnable examples demonstrating Dedalus MCP's capabilities. Each example is self-contained and tested.

## Quick Start

```bash
# Run any example
uv run python examples/showcase/01_minimal.py

# In another terminal
uv run python examples/showcase/01_client.py
```

## Directory Structure

```
examples/
├── showcase/           # Start here — hero examples
│   ├── 01_minimal.py          # 15-line server
│   ├── 01_client.py           # Script-style client
│   ├── 02_bidirectional_*     # Server asks client for LLM
│   ├── 03_realtime_*          # Hot-reload tools at runtime
│   └── run_all.sh             # Integration test script
│
├── capabilities/       # One example per MCP capability
│   ├── tools/                 # Typed tools, tags, filtering
│   ├── resources/             # Static, templates
│   ├── prompts/               # Message templates
│   ├── sampling/              # Server → Client LLM requests
│   └── elicitation/           # Server → Client user input
│
├── integrations/       # Framework migrations
│   └── fastapi_migration.py   # FastAPI → MCP pattern
│
├── patterns/           # Design patterns
│   ├── context_vs_script.py   # Client lifecycle styles
│   └── testing.py             # pytest patterns
│
├── advanced/           # Power features
│   └── llm_chain.py           # MCP server chaining
│
├── client/             # Client-specific examples
│   ├── basic_connect.py       # MCPClient.connect()
│   ├── dpop_auth.py           # DPoP authentication
│   └── bearer_auth.py         # Bearer token auth
│
└── auth/               # Authorization flows
    └── ...
```

## Dedalus MCP vs FastMCP

Dedalus MCP and FastMCP solve the same problem differently. Here's why we think our approach is better:

### Registration Model

**FastMCP** binds tools at decoration time:

```python
from fastmcp import FastMCP
mcp = FastMCP("server")

@mcp.tool  # Bound to `mcp` forever
def add(a: int, b: int) -> int:
    return a + b
```

**Dedalus MCP** separates decoration from registration:

```python
from dedalus_mcp import MCPServer, tool

@tool(description="Add numbers")  # Just metadata
def add(a: int, b: int) -> int:
    return a + b

# Register explicitly
server_a = MCPServer("a")
server_a.collect(add)

server_b = MCPServer("b")
server_b.collect(add)  # Same function, different server!
```

This matters because:
- **Testing**: No global state. Each test creates its own server.
- **Multi-server**: Same tools, multiple servers, different configs.
- **Modularity**: Import tools from anywhere, register where needed.

### Collection vs Binding

FastMCP requires re-decoration for multi-server:

```python
# FastMCP: awkward
mcp1 = FastMCP("server1")
mcp2 = FastMCP("server2")

@mcp1.tool
@mcp2.tool  # Double decoration
def shared_tool():
    pass
```

Dedalus MCP uses explicit collection:

```python
# Dedalus MCP: clean
@tool(description="Shared")
def shared_tool():
    pass

server1.collect(shared_tool)
server2.collect(shared_tool)
```

### Client Ergonomics

FastMCP requires context managers:

```python
# FastMCP
async with Client(mcp) as client:
    result = await client.call_tool("add", {"a": 1, "b": 2})
```

Dedalus MCP supports script-style:

```python
# Dedalus MCP
client = await MCPClient.connect("http://localhost:8000/mcp")
result = await client.call_tool("add", {"a": 1, "b": 2})
await client.close()  # Explicit, or use context manager
```

### Features

| Feature | Dedalus MCP | FastMCP |
|---------|---------|---------|
| Decoupled registration | ✅ | ❌ |
| Multi-server support | ✅ Native | Workarounds |
| Script-style client | ✅ | ❌ |
| DPoP auth (RFC 9449) | ✅ | ❌ |
| Server → Server chaining | ✅ | Possible |
| Real-time tool updates | ✅ | ✅ |
| Typed tools | ✅ | ✅ |
| Progress reporting | ✅ | ✅ |
| Sampling/Elicitation | ✅ | ✅ |

## Running Tests

Integration test all showcase examples:

```bash
./examples/showcase/run_all.sh
```

Run specific capability tests:

```bash
# Start server
uv run python examples/capabilities/tools/01_typed_tools.py &

# Test with client
uv run python examples/showcase/01_client.py
```

## Debugging with tmux

Run server and client in split panes:

```bash
# Create session
tmux new-session -d -s mcp 'uv run python examples/showcase/01_minimal.py'
tmux split-window -h 'sleep 2 && uv run python examples/showcase/01_client.py'
tmux attach -t mcp

# Cleanup
tmux kill-session -t mcp
```
