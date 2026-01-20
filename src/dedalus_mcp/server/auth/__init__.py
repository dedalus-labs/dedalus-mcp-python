# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Server-side authorization for MCP.

Configure authorization for protected MCP servers:

    >>> from dedalus_mcp import MCPServer
    >>> from dedalus_mcp.server.auth import AuthorizationConfig, JWTValidator
    >>>
    >>> server = MCPServer(
    ...     "my-server",
    ...     authorization=AuthorizationConfig(enabled=True),
    ... )
"""

from __future__ import annotations

from ..authorization import (
    AuthorizationConfig,
    AuthorizationContext,
    AuthorizationError,
    AuthorizationManager,
    AuthorizationProvider,
)
from ..services.jwt_validator import (
    ExpiredTokenError,
    InvalidAudienceError,
    InvalidIssuerError,
    InvalidJWTSignatureError,
    JWKSFetchError,
    JWTValidationError,
    JWTValidator,
    JWTValidatorConfig,
    MissingScopeError,
    PublicKeyNotFoundError,
)

__all__ = [
    # Config
    "AuthorizationConfig",
    "JWTValidatorConfig",
    # Validators
    "JWTValidator",
    "AuthorizationProvider",
    "AuthorizationManager",
    # Context
    "AuthorizationContext",
    # Errors
    "AuthorizationError",
    "JWTValidationError",
    "ExpiredTokenError",
    "InvalidAudienceError",
    "InvalidIssuerError",
    "InvalidJWTSignatureError",
    "JWKSFetchError",
    "MissingScopeError",
    "PublicKeyNotFoundError",
]
