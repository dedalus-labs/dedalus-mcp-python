# Registration Pattern

**Problem**: The MCP spec doesn't mandate *how* servers register tools, resources, and prompts—only what JSON-RPC messages they must answer. Most frameworks force you to call instance methods (`server.add_tool(fn)`) or use decorators that bind at decoration time (`@server.tool`). Both approaches leak server references into module globals or entangle registration with object lifetime. Multi-server scenarios become messy, and testability suffers when decorators hard-bind to a singleton.

**Solution**: Decorators (`@tool`, `@resource`, `@prompt`) attach metadata to functions *without* binding them to a server instance. Registration happens explicitly via `server.collect()`. This approach separates *declaration* (what the function is) from *registration* (which server it serves).

```python
from dedalus_mcp import MCPServer, tool

@tool(description="Add two numbers")
def add(a: int, b: int) -> int:
    return a + b

server = MCPServer("my-server")
server.collect(add)  # Registration happens here
```

Same function, multiple servers:

```python
server_a = MCPServer("service-a")
server_b = MCPServer("service-b")

server_a.collect(add)
server_b.collect(add)
```

**Dedalus MCP**: The `@tool`, `@resource`, `@prompt`, `@resource_template`, and `@completion` decorators attach metadata attributes (`__dedalus_mcp_tool__`, `__dedalus_mcp_resource__`, etc.). The `server.collect()` method extracts these specs and routes them to the appropriate registration method.

## Design Rationale

### Why Deferred Registration?

Instance decorators (`@server.tool`) couple the function to the server at decoration time, which happens at module import. This creates several problems:

1. **Import-time side effects**: The server must exist before you can import the module containing your tools. Circular dependencies proliferate.
2. **Single-server coupling**: The function is permanently bound to one server instance. Testing with mock servers or serving the same function from multiple servers requires awkward workarounds.
3. **Global state leakage**: Frameworks typically use a singleton pattern to make `server` available everywhere. This makes testing harder and violates separation of concerns.
4. **Unclear ownership**: When `@server.tool` executes at import time, the server's lifecycle is unclear. Did someone start it already? Is it safe to mutate?

Dedalus MCP inverts this: decorators attach metadata, and the server pulls that metadata when you call `collect()`. Benefits:

- **Explicit registration timing**: `server.collect(fn)` is a visible, testable boundary.
- **Multi-server support**: The same decorated function can be registered to multiple servers.
- **No import-time dependencies**: Decorators don't need the server to exist yet. Registration happens later, when you control it.
- **Script-friendly**: Define functions at module scope with decorators, wire them to a server imperatively. Familiar pattern.

## API Reference

### `server.collect(*fns)`

Register decorated functions with this server. Extracts metadata from each function and calls the appropriate registration method.

```python
server.collect(add, multiply, settings)
```

Accepts any callable decorated with `@tool`, `@resource`, `@resource_template`, `@prompt`, or `@completion`. Raises `ValueError` if a function lacks metadata.

### `server.collect_from(*modules)`

Register all decorated callables from one or more modules.

```python
from tools import math, text

server.collect_from(math, text)
```

Inspects each module for public callables with Dedalus MCP metadata. Functions without metadata are silently skipped.

### `extract_spec(fn)`

Extract Dedalus MCP metadata from a decorated function. Returns `None` if no metadata found.

```python
from dedalus_mcp import extract_spec

spec = extract_spec(add)  # ToolSpec instance
```

## Alternative: Binding Context

For dynamic scenarios where functions are defined at runtime, use `server.binding()`:

```python
with server.binding():
    @tool(description="Dynamic tool")
    def dynamic_fn() -> str:
        return "created at runtime"
```

Inside the binding context, decorators immediately register with the active server. This is useful for conditional registration based on config or environment.

### ContextVar Mechanics (Internal)

`server.binding()` uses Python's `contextvars.ContextVar` for task-local storage. Each capability maintains its own ContextVar to track the active server:

```python
# From src/dedalus_mcp/tool.py
_ACTIVE_SERVER: ContextVar[MCPServer | None] = ContextVar(
    "_dedalus_mcp_active_server", default=None
)
```

When a decorator executes inside a binding context:

1. It checks `get_active_server()` for an active server.
2. If found, it immediately calls `server.register_tool(spec)`.
3. If not found, it only attaches metadata to the function.

Most users should use `collect()`. The binding context is for power users and dynamic scenarios.

## When to Use `collect()` vs `binding()`

### Use `collect()` (Recommended)

For most cases, define functions at module scope and collect them:

```python
from dedalus_mcp import MCPServer, tool

@tool(description="Add two numbers")
def add(a: int, b: int) -> int:
    return a + b

@tool(description="Multiply two numbers")
def multiply(a: int, b: int) -> int:
    return a * b

server = MCPServer("calculator")
server.collect(add, multiply)
```

Clean, script-friendly, matches Python conventions.

### Use `binding()` for Dynamic Registration

When functions are defined at runtime (e.g., from config or webhooks), use `binding()`:

```python
async def add_tool_from_config(config: dict):
    with server.binding():
        @tool(description=config["description"])
        def dynamic_tool(**kwargs) -> str:
            return config["response"]

    await server.notify_tools_list_changed()
```

Inside `binding()`, decorators register immediately. Outside, they only attach metadata.

### Don't Use `binding()` During Request Handling

The binding context is for registration, not request handling:

```python
# WRONG: Don't bind during request handling
@server.list_tools()
async def list_handler(request):
    with server.binding():  # Wrong place
        @tool()
        def dynamic() -> str:
            return "confused"
```

Dynamic registration should happen outside request handlers, then notify clients:

```python
# Correct: Register first, then notify
async def add_tool_at_runtime():
    @tool(description="Added later")
    def late_arrival() -> str:
        return "added later"

    server.collect(late_arrival)
    await server.notify_tools_list_changed()
```

## Comparison to Other Patterns

### Global Registries

Some frameworks use global registries where decorators append to a module-level list:

```python
# Hypothetical global pattern
_TOOLS = []

def tool(fn):
    _TOOLS.append(fn)
    return fn

server.load_tools(_TOOLS)
```

**Problems**: Hidden state persists across test runs. Single registry. Import order matters.

### Instance Decorators

FastMCP uses `@mcp.tool` which binds at decoration time:

```python
mcp = FastMCP()

@mcp.tool  # Bound to mcp at import time
def add(a: int, b: int) -> int:
    return a + b
```

**Problems**: Function is coupled to that server instance. Multi-server scenarios require workarounds.

### Dedalus MCP's Approach

Decorators only attach metadata. You explicitly collect:

```python
@tool(description="Add")
def add(a: int, b: int) -> int:
    return a + b

server.collect(add)  # Registration happens here
```

**Benefits**: No global state. No import-time coupling. Same function, multiple servers.

## Same Function on Multiple Servers

Because decorators only attach metadata, the same function can be registered to multiple servers:

```python
from dedalus_mcp import MCPServer, tool

@tool(description="Shared multiplication")
def multiply(a: int, b: int) -> int:
    return a * b

server_a = MCPServer("service-a")
server_b = MCPServer("service-b")

server_a.collect(multiply)
server_b.collect(multiply)

print(server_a.tool_names)  # ["multiply"]
print(server_b.tool_names)  # ["multiply"]
```

Each server gets its own registration. The function object is shared. No state conflict.

## Examples

### Multi-Server Registration

Register shared utilities across multiple services:

```python
from dedalus_mcp import MCPServer, tool

@tool(description="Get current Unix timestamp")
def timestamp() -> int:
    from time import time
    return int(time())

@tool(description="Restart a service")
def restart_service(name: str) -> str:
    return f"Restarting {name}..."

@tool(description="Get API version")
def version() -> str:
    return "v1.2.3"

# Service 1: Internal utilities (timestamp + restart)
internal_server = MCPServer("internal-tools")
internal_server.collect(timestamp, restart_service)

# Service 2: Public API (timestamp + version)
public_server = MCPServer("public-api")
public_server.collect(timestamp, version)

print(internal_server.tool_names)  # ["timestamp", "restart_service"]
print(public_server.tool_names)    # ["timestamp", "version"]
```

### Dynamic Tool Registration

Add tools after the server starts:

```python
from dedalus_mcp import MCPServer, tool
import asyncio

@tool(description="Always available")
def base_tool() -> str:
    return "base"

server = MCPServer("dynamic", allow_dynamic_tools=True)
server.collect(base_tool)

async def add_tool_at_runtime():
    @tool(description="Added later")
    def dynamic_tool() -> str:
        return "dynamic"

    server.collect(dynamic_tool)
    await server.notify_tools_list_changed()

async def main():
    print("Initial tools:", server.tool_names)  # ["base_tool"]

    await add_tool_at_runtime()

    print("After dynamic add:", server.tool_names)  # ["base_tool", "dynamic_tool"]

asyncio.run(main())
```

### Conditional Registration

Register tools based on environment or config:

```python
from dedalus_mcp import MCPServer, tool
import os

@tool(description="Production-safe operation")
def safe_op() -> str:
    return "safe"

@tool(description="Dangerous debug operation")
def debug_op() -> str:
    return "debugging"

server = MCPServer("conditional")
server.collect(safe_op)

if os.getenv("ENABLE_DEBUG") == "1":
    server.collect(debug_op)
```

### Testing with Isolated Servers

Each test case gets a fresh server without shared state:

```python
from dedalus_mcp import MCPServer, tool
import pytest

@tool(description="Test fixture tool")
def test_tool() -> str:
    return "test"

@pytest.mark.asyncio
async def test_tool_registration():
    server = MCPServer("test-server")
    server.collect(test_tool)

    assert "test_tool" in server.tool_names

    result = await server.invoke_tool("test_tool")
    assert result.content[0].text == "test"

@pytest.mark.asyncio
async def test_another_server():
    # Completely isolated from the previous test
    another_server = MCPServer("another-test")
    another_server.collect(test_tool)

    assert "test_tool" in another_server.tool_names
```

### Cross-Module Registration

Organize tools in separate modules and register them all at once:

```python
# tools/math.py
from dedalus_mcp import tool

@tool(description="Add two numbers")
def add(a: int, b: int) -> int:
    return a + b

@tool(description="Multiply two numbers")
def multiply(a: int, b: int) -> int:
    return a * b

# tools/text.py
from dedalus_mcp import tool

@tool(description="Convert to uppercase")
def uppercase(text: str) -> str:
    return text.upper()

# server.py
from dedalus_mcp import MCPServer
from tools import math, text

server = MCPServer("multi-module")
server.collect_from(math, text)

print(server.tool_names)  # ["add", "multiply", "uppercase"]
```

## Internal Implementation Details

### Decorator Execution Flow

When you write `@tool()`, the decorator attaches metadata without registering:

```python
# Simplified from src/dedalus_mcp/tool.py
def tool(name=None, *, description=None, ...):
    def decorator(fn):
        spec = ToolSpec(name=name or fn.__name__, fn=fn, description=description, ...)
        setattr(fn, "__dedalus_mcp_tool__", spec)  # Attach metadata

        # Check for binding context (optional auto-registration)
        server = get_active_server()
        if server is not None:
            server.register_tool(spec)

        return fn
    return decorator
```

Key steps:

1. Create a `ToolSpec` dataclass with the function and metadata.
2. Attach the spec to the function as `__dedalus_mcp_tool__`.
3. Return the original function unchanged (no wrapping).

### `collect()` Implementation

The `collect()` method extracts metadata and routes to the appropriate registration:

```python
# From src/dedalus_mcp/server/core.py (simplified)
def collect(self, *fns):
    for fn in fns:
        spec = self._extract_spec(fn)
        if spec is None:
            raise ValueError(f"'{fn.__name__}' has no Dedalus MCP metadata")
        self._register_spec(spec)

def _extract_spec(self, fn):
    for extractor in (extract_tool_spec, extract_resource_spec, ...):
        spec = extractor(fn)
        if spec is not None:
            return spec
    return None

def _register_spec(self, spec):
    if isinstance(spec, ToolSpec):
        self.register_tool(spec)
    elif isinstance(spec, ResourceSpec):
        self.register_resource(spec)
    # ... etc
```

### Binding Context (Alternative)

The `server.binding()` context manager enables auto-registration for dynamic scenarios:

```python
@contextmanager
def binding(self):
    tool_token = set_tool_server(self)
    # ... set tokens for all capabilities
    try:
        yield self
    finally:
        reset_tool_server(tool_token)
        # ... reset all tokens
```

Inside `binding()`, decorators immediately register. Outside, they only attach metadata.

## See Also

- [Tools](tools.md) - Using the `@tool` decorator and schema inference
- [Resources](resources.md) - Using the `@resource` decorator for content serving
- [Prompts](prompts.md) - Using the `@prompt` decorator for template authoring
- [Schema Inference](schema-inference.md) - How Dedalus MCP generates JSON schemas from type hints
- [Result Normalization](result-normalization.md) - How function return values become MCP responses
- Official spec: [MCP Server Tools](https://modelcontextprotocol.io/specification/2025-06-18/server/tools)
- Official spec: [MCP Server Resources](https://modelcontextprotocol.io/specification/2025-06-18/server/resources)
- Official spec: [MCP Server Prompts](https://modelcontextprotocol.io/specification/2025-06-18/server/prompts)
