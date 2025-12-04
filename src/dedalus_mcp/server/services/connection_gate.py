# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Connection handle authorization gate.

This module provides authorization checks for connection handles based on
JWT claims. The `ddls:connections` claim lists which handles a session
is permitted to use when dispatching operations to the Enclave.

Key responsibilities:
- Parse `ddls:connections` claim from validated JWT claims
- Check if a requested handle is authorized
- Support wildcard patterns for flexible authorization
- Validate handle format

References:
    /dcs/apps/enclave/IMPLEMENTATION_SPEC.md (connection handle format)
"""

from __future__ import annotations

import fnmatch
import re
from typing import Any

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


class ConnectionHandleNotAuthorizedError(ConnectionHandleError):
    """Raised when a connection handle is not in the authorized set."""

    def __init__(self, handle: str) -> None:
        self.handle = handle
        super().__init__(f"connection handle not authorized: {handle}")


class InvalidConnectionHandleError(ConnectionHandleError):
    """Raised when a connection handle has an invalid format."""

    def __init__(self, handle: str) -> None:
        self.handle = handle
        super().__init__(f"invalid connection handle format: {handle}")


# =============================================================================
# Claim Parsing
# =============================================================================


def parse_connections_claim(claims: dict[str, Any]) -> set[str]:
    """Parse the ddls:connections claim from JWT claims.

    The claim can be:
    - A list of connection handle strings
    - A single connection handle string
    - Missing (treated as empty set)

    Non-string entries in a list are filtered out.

    Args:
        claims: JWT claims dictionary

    Returns:
        Set of authorized connection handle strings
    """
    raw = claims.get("ddls:connections")

    if raw is None:
        return set()

    if isinstance(raw, str):
        return {raw}

    if isinstance(raw, list):
        # Filter to only valid strings
        return {item for item in raw if isinstance(item, str)}

    # Unknown type, treat as empty
    _logger.warning(
        "unexpected ddls:connections claim type",
        extra={"event": "connection_gate.claim.invalid_type", "type": type(raw).__name__},
    )
    return set()


# =============================================================================
# Authorization Gate
# =============================================================================


class ConnectionHandleGate:
    """Authorizes connection handle usage based on JWT claims.

    The gate checks if a requested connection handle is in the authorized set
    derived from the `ddls:connections` JWT claim. Supports wildcard patterns
    for flexible authorization (e.g., `ddls:conn:*:github` matches any github
    connection).

    Example:
        >>> claims = {"ddls:connections": ["ddls:conn:01ABC-github"]}
        >>> gate = ConnectionHandleGate.from_claims(claims)
        >>> gate.check("ddls:conn:01ABC-github")  # OK
        >>> gate.check("ddls:conn:99XYZ-slack")   # Raises ConnectionHandleNotAuthorizedError
    """

    def __init__(
        self,
        authorized_handles: set[str],
        *,
        validate_format: bool = True,
    ) -> None:
        """Initialize the gate with authorized handles.

        Args:
            authorized_handles: Set of authorized connection handle strings.
                May include wildcard patterns using fnmatch syntax.
            validate_format: If True, validate handle format before checking.
        """
        self._authorized = frozenset(authorized_handles)
        self._validate_format = validate_format

        # Separate exact matches from wildcard patterns
        self._exact_handles: frozenset[str] = frozenset(
            h for h in self._authorized if "*" not in h and "?" not in h
        )
        self._wildcard_patterns: tuple[str, ...] = tuple(
            h for h in self._authorized if "*" in h or "?" in h
        )

    @classmethod
    def from_claims(cls, claims: dict[str, Any], **kwargs: Any) -> "ConnectionHandleGate":
        """Construct a gate from JWT claims.

        Args:
            claims: JWT claims dictionary containing ddls:connections
            **kwargs: Additional arguments passed to constructor

        Returns:
            ConnectionHandleGate configured with authorized handles from claims
        """
        handles = parse_connections_claim(claims)
        return cls(authorized_handles=handles, **kwargs)

    def check(self, handle: str) -> None:
        """Check if a connection handle is authorized.

        Args:
            handle: The connection handle to check

        Raises:
            InvalidConnectionHandleError: If handle format is invalid
            ConnectionHandleNotAuthorizedError: If handle is not authorized
        """
        # Validate format first
        if self._validate_format and not self._is_valid_format(handle):
            raise InvalidConnectionHandleError(handle)

        # Check exact match first (fast path)
        if handle in self._exact_handles:
            return

        # Check wildcard patterns
        for pattern in self._wildcard_patterns:
            if fnmatch.fnmatch(handle, pattern):
                return

        # Not authorized
        raise ConnectionHandleNotAuthorizedError(handle)

    def is_authorized(self, handle: str) -> bool:
        """Check if a handle is authorized without raising.

        Args:
            handle: The connection handle to check

        Returns:
            True if authorized, False otherwise
        """
        try:
            self.check(handle)
            return True
        except (InvalidConnectionHandleError, ConnectionHandleNotAuthorizedError):
            return False

    @property
    def authorized_handles(self) -> frozenset[str]:
        """Return the set of authorized handles (including patterns)."""
        return self._authorized

    @staticmethod
    def _is_valid_format(handle: str) -> bool:
        """Check if handle matches expected format."""
        return bool(_HANDLE_PATTERN.match(handle))


__all__ = [
    "ConnectionHandleGate",
    "parse_connections_claim",
    "ConnectionHandleError",
    "ConnectionHandleNotAuthorizedError",
    "InvalidConnectionHandleError",
]

