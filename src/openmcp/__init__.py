# ==============================================================================
#                  © 2025 Dedalus Labs, Inc. and affiliates
#                            Licensed under MIT
#               github.com/dedalus-labs/openmcp-python/LICENSE
# ==============================================================================

"""OpenMCP framework primitives.

This module exports the core API surface for building MCP servers and clients.
Advanced features like dependency injection, authorization configuration, and
context management are available through their respective submodules:

- ``openmcp.context`` - Context access and management
- ``openmcp.server.dependencies`` - Dependency injection utilities
- ``openmcp.server.authorization`` - Authorization configuration
- ``openmcp.server`` - Server configuration flags

See the module docstrings for detailed usage patterns.
"""

from __future__ import annotations

from ._sdk_loader import ensure_sdk_importable


ensure_sdk_importable()

from . import types
from .client import MCPClient
from .completion import CompletionResult, completion
from .context import Context, get_context
from .progress import progress
from .prompt import prompt
from .resource import resource
from .resource_template import resource_template
from .server import MCPServer
from .server.dependencies import register_injectable_type
from .tool import tool

# Register Context for auto-injection in dependencies
register_injectable_type(Context)


__all__ = [
    "MCPClient",
    "MCPServer",
    "tool",
    "resource",
    "completion",
    "CompletionResult",
    "prompt",
    "resource_template",
    "get_context",
    "progress",
    "types",
]
