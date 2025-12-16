# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Dedalus MCP framework primitives.

This module exports the core API surface for building MCP servers and clients.
Advanced features like dependency injection, authorization configuration, and
context management are available through their respective submodules:

- ``dedalus_mcp.context`` - Context access and management
- ``dedalus_mcp.server.dependencies`` - Dependency injection utilities
- ``dedalus_mcp.server.authorization`` - Authorization configuration
- ``dedalus_mcp.server`` - Server configuration flags

See the module docstrings for detailed usage patterns.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import TYPE_CHECKING, Any

from pydantic.types import T

from . import types
from .client import MCPClient
from .completion import (
    CompletionResult,
    CompletionSpec,
    completion,
    extract_completion_spec,
)
from .context import Context, get_context
from .dispatch import (
    DispatchError,
    DispatchErrorCode,
    DispatchResponse,
    HttpMethod,
    HttpRequest,
    HttpResponse,
)
from .progress import progress
from .prompt import PromptSpec, extract_prompt_spec, prompt
from .resource import ResourceSpec, extract_resource_spec, resource
from .resource_template import (
    ResourceTemplateSpec,
    extract_resource_template_spec,
    resource_template,
)
from .server import MCPServer
from .server.authorization import AuthorizationConfig
from .server.connectors import (
    Binding,
    Connection,
    SecretKeys,
    SecretValues,
)
from .server.dependencies import register_injectable_type
from .server.services.jwt_validator import JWTValidator, JWTValidatorConfig
from .tool import ToolSpec, extract_tool_spec, tool

if TYPE_CHECKING:
    from collections.abc import Callable

__version__ = version('dedalus_mcp')


# Register Context for auto-injection in dependencies, TODO: sus
register_injectable_type(Context)

# Type alias for any Dedalus MCP capability spec
CapabilitySpec = (
    ToolSpec | ResourceSpec | PromptSpec | CompletionSpec | ResourceTemplateSpec
)


def extract_spec(fn: Callable[..., Any]) -> CapabilitySpec | None:
    """Extract Dedalus MCP metadata from a decorated function.

    Returns the spec if the function was decorated with @tool, @resource,
    @prompt, @completion, or @resource_template. Returns None otherwise.

    Usage:
        @tool(description="Add numbers")
        def add(a: int, b: int) -> int:
            return a + b

        spec = extract_spec(add)  # ToolSpec instance
    """
    for extractor in (
        extract_tool_spec,
        extract_resource_spec,
        extract_prompt_spec,
        extract_completion_spec,
        extract_resource_template_spec,
    ):
        spec = extractor(fn)
        if spec is not None:
            return spec
    return None


__all__ = [
    # Core
    '__version__',
    'types',
    # Server
    'MCPServer',
    'MCPClient',
    'Context',
    'get_context',
    # Authorization
    'AuthorizationConfig',
    'JWTValidator',
    'JWTValidatorConfig',
    # Connections
    'Binding',
    'Connection',
    'SecretKeys',
    'SecretValues',
    # Dispatch
    'HttpMethod',
    'HttpRequest',
    'HttpResponse',
    'DispatchResponse',
    'DispatchError',
    'DispatchErrorCode',
    # Capabilities
    'CapabilitySpec',
    'ToolSpec',
    'ResourceSpec',
    'ResourceTemplateSpec',
    'PromptSpec',
    'CompletionSpec',
    'CompletionResult',
    # Decorators
    'tool',
    'resource',
    'resource_template',
    'prompt',
    'completion',
    'progress',
    'extract_spec',
]
