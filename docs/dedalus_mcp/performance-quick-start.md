# Performance Quick Start

## Installation

```bash
# Default (minimal)
uv add dedalus_mcp

# With performance optimizations (recommended for production)
uv add "dedalus_mcp[opt]"
```

## What You Get

Installing `dedalus_mcp[opt]` adds:

1. **uvloop** - 2-4x faster event loop (Unix/Linux only)
2. **orjson** - 2x faster JSON serialization (optional, for logging)

## Verification

Check if uvloop is active:

```bash
export DEDALUS_MCP_LOG_LEVEL=DEBUG
python your_server.py
```

Look for: `Event loop: uvloop` or `Event loop: asyncio`

## Zero Code Changes

uvloop is automatically installed and activated when available. Your code stays the same:

```python
from dedalus_mcp import MCPServer, tool

server = MCPServer("my-server")

@tool()
async def my_tool() -> str:
    return "works with both asyncio and uvloop"

# Same code, faster execution with dedalus_mcp[opt]
```

## Performance Impact

Expect 2-4x speedup on async-heavy workloads (network, database, file I/O). Sync tools see no difference.

See `docs/dedalus_mcp/performance.md` for detailed benchmarks and usage patterns.
