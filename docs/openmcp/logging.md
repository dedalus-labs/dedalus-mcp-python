# Logging

**Problem**: MCP exposes a `logging/setLevel` request so clients can tune verbosity at runtime. Wiring this manually requires JSON-RPC plumbing and consistent logger configuration across transports.

**Solution**: Provide a reusable logging setup that defaults to structured, colorized output and implement the `logging/setLevel` handler so clients can switch levels without restarting the server.

**OpenMCP**: Use `openmcp.utils.get_logger` to obtain a Rich-powered logger and decorate a coroutine with `@server.set_logging_level()` to accept `logging/setLevel` requests. The helper adjusts both the server logger and the root logging level, mirroring the `docs/mcp/spec/schema-reference/logging-setlevel.md` contract.

```python
from openmcp import MCPServer
from openmcp.utils import get_logger

server = MCPServer("logging-demo")
log = get_logger("demo")

@server.set_logging_level()
async def adjust(level: str) -> None:
    log.info("Setting log level to %s", level)
```

- Spec receipts: `docs/mcp/spec/schema-reference/logging-setlevel.md`, `docs/mcp/capabilities/logging`
- Color scheme mirrors `api-final/src/common/logger.py`; override via `OPENMCP_LOG_LEVEL` or your own `logging` config if desired.
