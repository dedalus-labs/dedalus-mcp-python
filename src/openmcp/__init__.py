"""OpenMCP framework primitives."""

from __future__ import annotations

from ._sdk_loader import ensure_sdk_importable

ensure_sdk_importable()

from . import types
from .client import MCPClient
from .server import NotificationFlags, MCPServer
from .tool import tool
from .resource import resource
from .completion import completion, CompletionResult
from .prompt import prompt
from .resource_template import resource_template

__all__ = [
    "NotificationFlags",
    "MCPClient",
    "MCPServer",
    "tool",
    "resource",
    "completion",
    "CompletionResult",
    "prompt",
    "resource_template",
    "types",
]
