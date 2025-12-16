# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Tests for connection handle format validation.

Authorization is handled by the enclave gateway at runtime via Admin API.
The SDK only validates handle format - it does not authorize handles locally.
"""

from __future__ import annotations

import pytest

from dedalus_mcp.server.services.connection_gate import (
    InvalidConnectionHandleError,
    is_valid_handle_format,
    validate_handle_format,
)


class TestConnectionHandleFormat:
    """Tests for connection handle format validation."""

    def test_valid_standard_handle(self):
        """Standard handles (ddls:conn:...) should be valid."""
        assert is_valid_handle_format("ddls:conn:01ABC-github")
        assert is_valid_handle_format("ddls:conn:02DEF-slack")
        assert is_valid_handle_format("ddls:conn:99XYZ-supabase")

    def test_valid_env_handle(self):
        """Environment-backed handles (ddls:conn_env_...) should be valid."""
        assert is_valid_handle_format("ddls:conn_env_supabase_service_key")
        assert is_valid_handle_format("ddls:conn_env_github_token")

    def test_invalid_handle_format(self):
        """Invalid formats should be rejected."""
        assert not is_valid_handle_format("invalid-handle")
        assert not is_valid_handle_format("github")
        assert not is_valid_handle_format("")
        assert not is_valid_handle_format("ddls:connection:01ABC")  # wrong prefix

    def test_validate_raises_on_invalid(self):
        """validate_handle_format should raise InvalidConnectionHandleError."""
        with pytest.raises(InvalidConnectionHandleError) as exc_info:
            validate_handle_format("invalid-handle")

        assert exc_info.value.handle == "invalid-handle"
        assert "invalid connection handle format" in str(exc_info.value)

    def test_validate_passes_on_valid(self):
        """validate_handle_format should not raise on valid handles."""
        # Should not raise
        validate_handle_format("ddls:conn:01ABC-github")
        validate_handle_format("ddls:conn_env_supabase_service_key")
