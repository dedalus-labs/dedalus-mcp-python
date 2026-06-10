# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""MCP client implementation.

Provides ``MCPClient`` for connecting to MCP servers, plus helpers for
authentication, transports, and error handling.

Example:
    >>> async with await MCPClient.connect(
    ...     "http://localhost:8000/mcp"
    ... ) as client:
    ...     tools = await client.list_tools()
"""

from __future__ import annotations

from dedalus_mcp.auth.dpop import BearerAuth, DPoPAuth, generate_dpop_proof

from .connection import open_connection
from .core import ClientCapabilitiesConfig, MCPClient
from .diagnostics import ClientRequestHistory, ClientRequestRecord
from .errors import (
    AuthRequiredError,
    BadRequestError,
    ForbiddenError,
    MCPConnectionError,
    ServerError,
    SessionExpiredError,
    TransportError,
)
from .transports import lambda_http_client


__all__ = [
    "AuthRequiredError",
    "BadRequestError",
    "BearerAuth",
    "ClientCapabilitiesConfig",
    "ClientRequestHistory",
    "ClientRequestRecord",
    "DPoPAuth",
    "ForbiddenError",
    "MCPClient",
    "MCPConnectionError",
    "ServerError",
    "SessionExpiredError",
    "TransportError",
    "generate_dpop_proof",
    "lambda_http_client",
    "open_connection",
]
