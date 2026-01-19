# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Public server-side surface for Dedalus MCP.

The heavy lifting lives in :mod:`dedalus_mcp.server.core`; this module re-exports
the framework primitives that host applications are expected to import.
"""

from __future__ import annotations

from mcp.server.transport_security import TransportSecuritySettings

from .authorization import AuthorizationConfig
from .config import ElicitationConfig, PingConfig, SamplingConfig, ServerConfig
from .core import MCPServer, NotificationFlags, ServerValidationError, TransportLiteral
from .execution_plan import ExecutionPlan, build_plan_from_claims
from .notifications import DefaultNotificationSink, NotificationSink
from .transports import ASGIRunConfig


__all__ = [
    # Core
    "MCPServer",
    "NotificationFlags",
    "ServerValidationError",
    "TransportLiteral",
    # Config
    "ServerConfig",
    "SamplingConfig",
    "ElicitationConfig",
    "PingConfig",
    # Transport
    "TransportSecuritySettings",
    "ASGIRunConfig",
    # Authorization
    "AuthorizationConfig",
    # Execution
    "ExecutionPlan",
    "build_plan_from_claims",
    # Notifications
    "NotificationSink",
    "DefaultNotificationSink",
]
