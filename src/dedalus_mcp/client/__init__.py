# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Public client-side helpers for Dedalus MCP.

The implementation details live in :mod:`dedalus_mcp.client.core` and related
modules; this wrapper exposes the pieces that most applications use.
"""

from __future__ import annotations

from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream

from mcp.shared._httpx_utils import McpHttpClientFactory, create_mcp_http_client
from mcp.shared.message import SessionMessage

from dedalus_mcp.dpop import BearerAuth, DPoPAuth, generate_dpop_proof
from dedalus_mcp.types import (
    CreateMessageRequestParams,
    CreateMessageResult,
    ElicitRequestParams,
    ElicitResult,
    ErrorData,
    Implementation,
    LoggingMessageNotificationParams,
    Root,
)

from .connection import open_connection
from .core import (
    ClientCapabilitiesConfig,
    ElicitationHandler,
    LoggingHandler,
    MCPClient,
    SamplingHandler,
)
from .transports import lambda_http_client


__all__ = [
    "BearerAuth",
    "ClientCapabilitiesConfig",
    "CreateMessageRequestParams",
    "CreateMessageResult",
    "DPoPAuth",
    "ElicitRequestParams",
    "ElicitResult",
    "ElicitationHandler",
    "ErrorData",
    "Implementation",
    "LoggingHandler",
    "LoggingMessageNotificationParams",
    "MCPClient",
    "McpHttpClientFactory",
    "MemoryObjectReceiveStream",
    "MemoryObjectSendStream",
    "Root",
    "SamplingHandler",
    "SessionMessage",
    "create_mcp_http_client",
    "generate_dpop_proof",
    "lambda_http_client",
    "open_connection",
]
