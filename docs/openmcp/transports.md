# Transports

**Problem**: MCP transports (STDIO, Streamable HTTP) have different wiring requirements. Implementing the handshake, session lifecycle, and error handling for each by hand is tedious and easy to get wrong.

**Solution**: Wrap the reference SDK transport helpers with a simple dispatcher that defaults to Streamable HTTP but supports STDIO (and future transports) through a single `serve()` entry point.

**OpenMCP**: `MCPServer.serve()` inspects the configured transport (default `streamable-http`) and delegates to `serve_streamable_http` or `serve_stdio`. You can override the default by passing `transport="stdio"` when constructing the server or calling `serve(transport="stdio")` explicitly.

```python
server = MCPServer("demo", transport="stdio")

if __name__ == "__main__":
    import asyncio
    asyncio.run(server.serve())        # uses stdio because of constructor
    # asyncio.run(server.serve(transport="streamable-http"))  # override on demand
```

- Streamable HTTP helper (`serve_streamable_http`) maps to `docs/mcp/spec/overview/messages.md` and the reference SDK’s manager classes.
- STDIO helper (`serve_stdio`) keeps parity with CLI workflows.
- When adding new transports, funnel them through `serve()` so tooling can rely on a single entry point.
