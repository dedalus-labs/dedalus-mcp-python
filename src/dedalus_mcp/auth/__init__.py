# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Dedalus MCP authentication primitives.

This module provides the core credential and connection types for MCP servers.

Usage:
    from dedalus_mcp.auth import Connection, SecretKeys, Binding, SecretValues

    # Define what secrets a connection needs
    github = Connection(
        'github',
        secrets=SecretKeys(token='GITHUB_TOKEN'),
        base_url='https://api.github.com',
    )

    # At runtime, bind actual secret values
    secrets = SecretValues(github, token='ghp_xxx')
"""

from __future__ import annotations

# Re-export from server.connectors (canonical location)
from ..server.connectors import (
    Binding,
    Connection,
    SecretKeys,
    SecretValues,
)

__all__ = [
    "Binding",
    "Connection",
    "SecretKeys",
    "SecretValues",
]
