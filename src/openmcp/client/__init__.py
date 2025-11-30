# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Public client-side helpers for OpenMCP.

The implementation details live in :mod:`openmcp.client.core` and related
modules; this wrapper exposes the pieces that most applications use.
"""

from __future__ import annotations

from .core import ClientCapabilitiesConfig, MCPClient
from .connection import open_connection
from .transports import lambda_http_client


__all__ = [
    "MCPClient",
    "ClientCapabilitiesConfig",
    "lambda_http_client",
    "open_connection",
]
