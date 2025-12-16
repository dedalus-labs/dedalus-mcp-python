# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Public client-side helpers for Dedalus MCP.

The implementation details live in :mod:`dedalus_mcp.client.core` and related
modules; this wrapper exposes the pieces that most applications use.
"""

from __future__ import annotations

from dedalus_mcp.dpop import BearerAuth, DPoPAuth, generate_dpop_proof
from .connection import open_connection
from .core import ClientCapabilitiesConfig, MCPClient
from .transports import lambda_http_client


__all__ = [
    "BearerAuth",
    "ClientCapabilitiesConfig",
    "DPoPAuth",
    "MCPClient",
    "generate_dpop_proof",
    "lambda_http_client",
    "open_connection",
]
