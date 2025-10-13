# Getting Started with OpenMCP

**Problem**: Building a spec-compliant MCP server from scratch requires wiring the reference SDK, handling initialization responses, and juggling transport setup before you can expose a single tool or resource.

**Solution**: Standardize the bootstrapping workflow so every project gets the MCP handshake, capability advertisement, and transport selection right, without rewriting the same scaffolding.

**OpenMCP**: `MCPServer` wraps the reference SDK with opinionated defaults. You supply a server name (plus optional metadata) and register capabilities within a short `collecting()` scope. Streamable HTTP is the default transport, but `serve(transport="stdio")` gives you parity with CLI runtimes.

```python
from openmcp import MCPServer, tool

server = MCPServer(
    "demo",
    instructions="Example MCP server",
    version="0.1.0",
)

with server.collecting():
    @tool(description="Adds two numbers")
    def add(a: int, b: int) -> int:
        return a + b

if __name__ == "__main__":
    import asyncio
    asyncio.run(server.serve())  # defaults to Streamable HTTP
```

- Handshake receipts: `docs/mcp/core/lifecycle/lifecycle-phases.md`
- Transport helpers map to `docs/mcp/spec/overview/messages.md`
- Capability negotiation is surfaced via `NotificationFlags` and exposed through `create_initialization_options()`
