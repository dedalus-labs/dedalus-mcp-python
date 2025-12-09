# Python Style Guide

[Overview](README.md) | [Guide](guide.md) | [Best Practices](best-practices.md) | [Reference](reference.md)

This document is **normative and canonical**. It outlines the foundation of Python style at Dedalus.

## Style Principles

Readable Python code has these attributes, in order of importance:

1. **[Clarity](#clarity)** — The code's purpose is obvious to readers
2. **[Simplicity](#simplicity)** — It accomplishes its goal the simplest way possible
3. **[Concision](#concision)** — High signal-to-noise ratio
4. **[Maintainability](#maintainability)** — Easy to modify correctly
5. **[Consistency](#consistency)** — Looks like the rest of the codebase

### Clarity

The goal: readers understand what the code does and why.

**What is this code doing?**

- Use descriptive variable names
- Add comments that explain non-obvious logic
- Break up dense code with whitespace
- Extract complex logic into well-named functions

**Why is it doing that?**

Comments should explain *why*, not *what*:

```python
# Bad: Describes what the code does (obvious from reading it)
# Increment counter by one
counter += 1

# Good: Explains why
# Track retry attempts to implement exponential backoff
retry_count += 1
```

### Simplicity

Write code for the people who will use, read, and maintain it.

Simple code:

- Reads top to bottom without backtracking
- Doesn't assume prior knowledge
- Has no unnecessary abstraction
- Uses mundane names for mundane things
- Is rarely "clever"

#### Least Mechanism

When multiple approaches work, prefer the simplest tool:

1. Built-in types (list, dict, set)
2. Standard library
3. Well-established packages (Pydantic, httpx)

Don't import a library for something the stdlib does well.

### Concision

Concise code has high signal-to-noise ratio:

```python
# Bad: Verbose
result_list = []
for item in items:
    if item.is_valid:
        result_list.append(item.value)

# Good: Concise
result = [item.value for item in items if item.is_valid]
```

But don't sacrifice clarity for brevity:

```python
# Bad: Too clever
x = a if b else c if d else e

# Good: Clear
if b:
    x = a
elif d:
    x = c
else:
    x = e
```

### Maintainability

Code is edited far more than it's written.

Maintainable code:

- Is easy to modify correctly
- Has APIs that grow gracefully
- Avoids unnecessary coupling
- Has comprehensive tests

### Consistency

Match the patterns already in the codebase. When the style guide doesn't cover something, match nearby code.

## Core Guidelines

### Formatting

All code must be formatted with `ruff format`. No exceptions.

[ruff](https://docs.astral.sh/ruff/) is a Rust-based linter and formatter that's 10-100x faster than traditional tools. It replaces Black, isort, Flake8, and dozens of plugins with a single, fast tool.

```bash
uv run ruff format .      # Format code
uv run ruff check . --fix # Lint and auto-fix
```

### Line Length

120 characters maximum (configured in `pyproject.toml`).

If a line feels too long, consider:

- Extracting variables
- Breaking into multiple statements
- Splitting function arguments

### Imports

Order imports in groups, separated by blank lines:

```python
# Future imports (if needed)
from __future__ import annotations

# Standard library
import asyncio
import logging
from collections.abc import Callable, Sequence
from typing import Any, TypeVar

# Third-party packages
from pydantic import BaseModel, Field

# Local imports
from dedalus_mcp.context import Context, get_context
from dedalus_mcp.types import Tool, Resource
```

Don't use relative imports except within a package:

```python
# Bad (from outside the package)
from ..utils import helper

# Good
from dedalus_mcp.utils import helper
```

### Naming

| Type | Convention | Example |
|------|------------|---------|
| Module | `snake_case` | `resource_template.py` |
| Package | `snake_case` | `dedalus_mcp/server/` |
| Class | `PascalCase` | `MCPServer`, `ToolService` |
| Exception | `PascalCase` + `Error` | `ResourceNotFoundError` |
| Function | `snake_case` | `get_context()`, `register_tool()` |
| Method | `snake_case` | `server.run()` |
| Variable | `snake_case` | `tool_name`, `request_id` |
| Constant | `SCREAMING_SNAKE` | `DEFAULT_TIMEOUT`, `MAX_RETRIES` |
| Type variable | `PascalCase` | `T`, `ResponseT` |
| Private | `_leading_underscore` | `_internal_cache` |

**Abbreviations:**

- Treat acronyms as words: `HttpClient`, not `HTTPClient`
- Exception: `MCP` stays uppercase: `MCPServer`, `MCPClient`

**Avoid:**

- Single-letter names except for trivial loops: `for i in range(10)`
- Names that shadow builtins: `list`, `type`, `id`

### Type Hints

Required for all public APIs. We use [mypy](https://mypy.readthedocs.io/) for static type checking (migrating to [ty](https://github.com/astral-sh/ty) when it reaches beta):

```bash
uv run mypy src/dedalus_mcp
```

```python
def register_tool(
    name: str,
    handler: Callable[..., Any],
    *,
    description: str | None = None,
    schema: dict[str, Any] | None = None,
) -> Tool:
    """Register a tool with the server."""
    ...
```

Use modern syntax (Python 3.10+):

```python
# Good: Modern syntax
def process(items: list[str]) -> dict[str, int]:
    ...

# Avoid: Old typing module generics
from typing import List, Dict
def process(items: List[str]) -> Dict[str, int]:
    ...
```

For optional parameters:

```python
# Good: Union with None
def fetch(url: str, timeout: float | None = None) -> Response:
    ...

# Also good for complex defaults
def configure(settings: Settings | None = None) -> None:
    if settings is None:
        settings = Settings()
```

### Docstrings

Use Google style docstrings:

```python
def fetch_resource(
    uri: str,
    *,
    timeout: float = 30.0,
    validate: bool = True,
) -> Resource:
    """Fetch a resource by URI.

    Retrieves the resource from the configured backend, optionally
    validating the response against the schema.

    Args:
        uri: The resource URI to fetch (e.g., "file:///path/to/file").
        timeout: Request timeout in seconds.
        validate: Whether to validate the response.

    Returns:
        The fetched resource with contents populated.

    Raises:
        ResourceNotFoundError: If the resource doesn't exist.
        ValidationError: If validation is enabled and fails.
        TimeoutError: If the request exceeds the timeout.

    Example:
        >>> resource = fetch_resource("file:///etc/hosts")
        >>> print(resource.contents)
    """
```

**When to write docstrings:**

- All public modules, classes, functions, methods
- Complex private functions
- Any non-obvious behavior

**When to skip:**

- Trivial methods like `__repr__`
- Private methods with obvious behavior
- Test functions (unless complex)

### Error Handling

Be specific about exceptions:

```python
# Bad: Catches everything
try:
    result = process(data)
except Exception:
    log.error("Processing failed")

# Good: Catches specific exceptions
try:
    result = process(data)
except ValidationError as e:
    log.error("Invalid input: %s", e)
except TimeoutError:
    log.error("Processing timed out")
```

Use custom exceptions for domain errors:

```python
class ToolNotFoundError(Exception):
    """Raised when a requested tool doesn't exist."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Tool not found: {name}")
```

### Async Code

Use `async`/`await` consistently:

```python
# Good: Async all the way
async def fetch_all(urls: list[str]) -> list[Response]:
    async with httpx.AsyncClient() as client:
        tasks = [client.get(url) for url in urls]
        return await asyncio.gather(*tasks)

# Bad: Mixing sync and async
def fetch_all(urls: list[str]) -> list[Response]:
    return asyncio.run(async_fetch_all(urls))  # Avoid
```

### Testing

Tests live in `tests/` mirroring `src/` structure:

```
src/dedalus_mcp/server/core.py
tests/test_server.py  # or tests/server/test_core.py
```

Use descriptive test names:

```python
# Good: Describes behavior
def test_tool_returns_error_on_invalid_input():
    ...

def test_resource_template_expands_uri_parameters():
    ...

# Bad: Vague
def test_tool():
    ...
```

Use pytest fixtures and parametrize:

```python
@pytest.fixture
def server():
    return MCPServer(name="test")

@pytest.mark.parametrize("input,expected", [
    ("hello", "HELLO"),
    ("world", "WORLD"),
])
def test_uppercase_tool(server, input, expected):
    result = server.call_tool("uppercase", {"text": input})
    assert result == expected
```

## Local Consistency

When the style guide doesn't cover something, match nearby code:

**Valid local choices:**

- Using `%s` vs f-strings for logging
- Exception message formatting
- Test organization patterns

**Invalid local choices:**

- Ignoring type hints
- Different naming conventions
- Skipping docstrings on public APIs

