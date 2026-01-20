# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""TDD tests for MCPServer connections parameter.

Tests the API where servers declare connection dependencies via connections=[...].
"""

from __future__ import annotations

import pytest


# =============================================================================
# MCPServer Connections Tests
# =============================================================================


class TestMCPServerConnections:
    """Tests for MCPServer connections parameter."""

    def test_single_connection(self):
        """MCPServer should accept single connection in list."""
        from dedalus_mcp import Connection, MCPServer, SecretKeys

        github = Connection("github", secrets=SecretKeys(token="GITHUB_TOKEN"))

        server = MCPServer(name="github-tools", connections=[github])

        assert "github" in server.connections
        assert server.connections["github"] is github

    def test_multiple_connections(self):
        """MCPServer should accept multiple connections."""
        from dedalus_mcp import Connection, MCPServer, SecretKeys

        github = Connection("github", secrets=SecretKeys(token="GITHUB_TOKEN"))
        openai = Connection("openai", secrets=SecretKeys(api_key="OPENAI_API_KEY"))

        server = MCPServer(name="multi-tools", connections=[github, openai])

        assert len(server.connections) == 2
        assert server.connections["github"] is github
        assert server.connections["openai"] is openai

    def test_empty_connections_allowed(self):
        """MCPServer should accept empty connections list."""
        from dedalus_mcp import MCPServer

        server = MCPServer(name="no-connections", connections=[])

        assert server.connections == {}

    def test_no_connections_param_defaults_empty(self):
        """MCPServer without connections param should have empty dict."""
        from dedalus_mcp import MCPServer

        server = MCPServer(name="standalone")

        assert hasattr(server, "connections")
        assert server.connections == {}


# =============================================================================
# MCPServer Connection Validation Tests
# =============================================================================


class TestMCPServerConnectionValidation:
    """Tests for connection validation."""

    def test_duplicate_names_rejected(self):
        """MCPServer should reject duplicate connection names."""
        from dedalus_mcp import Connection, MCPServer, SecretKeys

        conn1 = Connection("api", secrets=SecretKeys(key="KEY1"))
        conn2 = Connection("api", secrets=SecretKeys(key="KEY2"))

        with pytest.raises(ValueError) as exc:
            MCPServer(name="dupe-names", connections=[conn1, conn2])

        assert "duplicate" in str(exc.value).lower()
