# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Connection handle format validation."""

from __future__ import annotations

import re

from ...utils import get_logger


_logger = get_logger("dedalus_mcp.connection_gate")

# Connection handle patterns
# Standard: ddls:conn:ULID-provider (e.g., ddls:conn:01ABC123-github)
# Env-backed: ddls:conn_env_provider_auth (e.g., ddls:conn_env_supabase_service_key)
_HANDLE_PATTERN = re.compile(r"^ddls:conn[_:][\w\-]+$")


# =============================================================================
# Error Types
# =============================================================================


class ConnectionHandleError(Exception):
    """Base error for connection handle operations."""


class InvalidConnectionHandleError(ConnectionHandleError):
    """Raised when a connection handle has an invalid format."""

    def __init__(self, handle: str) -> None:
        self.handle = handle
        super().__init__(f"invalid connection handle format: {handle}")


# =============================================================================
# Format Validation
# =============================================================================


def is_valid_handle_format(handle: str) -> bool:
    """Check if handle matches expected format.

    Args:
        handle: Connection handle string to validate

    Returns:
        True if format is valid, False otherwise
    """
    return bool(_HANDLE_PATTERN.match(handle))


def validate_handle_format(handle: str) -> None:
    """Validate handle format, raising if invalid.

    Args:
        handle: Connection handle string to validate

    Raises:
        InvalidConnectionHandleError: If handle format is invalid
    """
    if not is_valid_handle_format(handle):
        raise InvalidConnectionHandleError(handle)


__all__ = ["ConnectionHandleError", "InvalidConnectionHandleError", "is_valid_handle_format", "validate_handle_format"]
