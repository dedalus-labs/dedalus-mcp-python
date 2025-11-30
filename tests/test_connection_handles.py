# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Tests for connection handle authorization from JWT claims.

The `ddls:connections` claim in access tokens lists which connection handles
a session is authorized to use. This module tests the parsing and validation
of these claims to ensure secure access control.
"""

from __future__ import annotations

import pytest

from openmcp.server.services.connection_gate import (
    ConnectionHandleGate,
    parse_connections_claim,
    ConnectionHandleNotAuthorizedError,
    InvalidConnectionHandleError,
)


class TestConnectionsClaimParsing:
    """Tests for parsing ddls:connections claim from JWT claims."""

    def test_parse_list_of_handles(self):
        """A list of connection handle strings should parse correctly."""
        claims = {"sub": "user123", "ddls:connections": ["ddls:conn:01ABC-github", "ddls:conn:02DEF-slack"]}

        handles = parse_connections_claim(claims)

        assert handles == {"ddls:conn:01ABC-github", "ddls:conn:02DEF-slack"}

    def test_parse_empty_list(self):
        """Empty list means no connections authorized."""
        claims = {"sub": "user123", "ddls:connections": []}

        handles = parse_connections_claim(claims)

        assert handles == set()

    def test_parse_missing_claim(self):
        """Missing claim means no connections authorized."""
        claims = {"sub": "user123"}

        handles = parse_connections_claim(claims)

        assert handles == set()

    def test_parse_single_string_converts_to_set(self):
        """A single string value should be converted to a single-item set."""
        claims = {"sub": "user123", "ddls:connections": "ddls:conn:01ABC-github"}

        handles = parse_connections_claim(claims)

        assert handles == {"ddls:conn:01ABC-github"}

    def test_parse_filters_invalid_entries(self):
        """Non-string entries in the list should be filtered out."""
        claims = {
            "sub": "user123",
            "ddls:connections": [
                "ddls:conn:01ABC-github",
                123,  # invalid
                None,  # invalid
                "ddls:conn:02DEF-slack",
            ],
        }

        handles = parse_connections_claim(claims)

        assert handles == {"ddls:conn:01ABC-github", "ddls:conn:02DEF-slack"}


class TestConnectionHandleGate:
    """Tests for connection handle authorization checks."""

    def test_authorized_handle_allowed(self):
        """A handle in the authorized set should pass."""
        gate = ConnectionHandleGate(authorized_handles={"ddls:conn:01ABC-github", "ddls:conn:02DEF-slack"})

        # Should not raise
        gate.check("ddls:conn:01ABC-github")

    def test_unauthorized_handle_rejected(self):
        """A handle not in the authorized set should be rejected."""
        gate = ConnectionHandleGate(authorized_handles={"ddls:conn:01ABC-github"})

        with pytest.raises(ConnectionHandleNotAuthorizedError) as exc_info:
            gate.check("ddls:conn:99XYZ-unknown")

        assert "ddls:conn:99XYZ-unknown" in str(exc_info.value)

    def test_empty_authorized_set_rejects_all(self):
        """With no authorized handles, all requests should be rejected."""
        gate = ConnectionHandleGate(authorized_handles=set())

        with pytest.raises(ConnectionHandleNotAuthorizedError):
            gate.check("ddls:conn:01ABC-github")

    def test_wildcard_pattern_matches(self):
        """Wildcard pattern should match multiple handles."""
        # Pattern "ddls:conn:*-github" should match any github connection
        gate = ConnectionHandleGate(authorized_handles={"ddls:conn:*-github"})

        # Should not raise
        gate.check("ddls:conn:01ABC-github")
        gate.check("ddls:conn:99XYZ-github")

    def test_wildcard_pattern_no_false_positive(self):
        """Wildcard pattern should not match unrelated handles."""
        gate = ConnectionHandleGate(authorized_handles={"ddls:conn:*-github"})

        with pytest.raises(ConnectionHandleNotAuthorizedError):
            gate.check("ddls:conn:01ABC-slack")  # Not github

    def test_from_claims_factory(self):
        """Factory method should construct gate from JWT claims."""
        claims = {"sub": "user123", "ddls:connections": ["ddls:conn:01ABC-github"]}

        gate = ConnectionHandleGate.from_claims(claims)

        # Should not raise for authorized handle
        gate.check("ddls:conn:01ABC-github")


class TestConnectionHandleFormat:
    """Tests for connection handle format validation."""

    def test_valid_handle_format_accepted(self):
        """Handles matching ddls:conn:... pattern should be accepted."""
        gate = ConnectionHandleGate(authorized_handles={"ddls:conn:01ABC-github"})

        # Should not raise
        gate.check("ddls:conn:01ABC-github")

    def test_invalid_handle_format_rejected(self):
        """Handles not matching expected pattern should be rejected."""
        gate = ConnectionHandleGate(authorized_handles={"ddls:conn:01ABC-github"})

        with pytest.raises(InvalidConnectionHandleError):
            gate.check("invalid-handle-format")

    def test_env_handle_format_accepted(self):
        """Environment-backed handles (ddls:conn_env_...) should be valid."""
        gate = ConnectionHandleGate(authorized_handles={"ddls:conn_env_supabase_service_key"})

        # Should not raise
        gate.check("ddls:conn_env_supabase_service_key")
