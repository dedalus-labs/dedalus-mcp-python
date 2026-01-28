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

    def test_single_connection_unnamed_allowed(self):
        """Single connection with empty name is allowed (auto-dispatch pattern)."""
        from dedalus_mcp import Connection, MCPServer, SecretKeys

        # name="" is the default for single-connection servers
        unnamed = Connection(secrets=SecretKeys(token="TOKEN"))

        server = MCPServer(name="single-unnamed", connections=[unnamed])

        assert "" in server.connections
        assert server.connections[""] is unnamed

    def test_multi_connection_unnamed_rejected(self):
        """Multi-connection servers must have names for all connections."""
        from dedalus_mcp import Connection, MCPServer, SecretKeys

        unnamed1 = Connection(secrets=SecretKeys(token="TOKEN1"))
        unnamed2 = Connection(secrets=SecretKeys(token="TOKEN2"))

        with pytest.raises(ValueError) as exc:
            MCPServer(name="multi-unnamed", connections=[unnamed1, unnamed2])

        assert "require all connections to have names" in str(exc.value)

    def test_multi_connection_partial_unnamed_rejected(self):
        """Multi-connection servers reject mix of named and unnamed."""
        from dedalus_mcp import Connection, MCPServer, SecretKeys

        named = Connection("github", secrets=SecretKeys(token="GITHUB_TOKEN"))
        unnamed = Connection(secrets=SecretKeys(token="SLACK_TOKEN"))

        with pytest.raises(ValueError) as exc:
            MCPServer(name="partial-unnamed", connections=[named, unnamed])

        assert "require all connections to have names" in str(exc.value)

    def test_multi_connection_all_named_allowed(self):
        """Multi-connection servers with all named connections work."""
        from dedalus_mcp import Connection, MCPServer, SecretKeys

        github = Connection("github", secrets=SecretKeys(token="GITHUB_TOKEN"))
        slack = Connection("slack", secrets=SecretKeys(token="SLACK_TOKEN"))

        server = MCPServer(name="multi-named", connections=[github, slack])

        assert len(server.connections) == 2
        assert "github" in server.connections
        assert "slack" in server.connections


# =============================================================================
# MCPServer Authorization Server Tests (RFC 9728)
# =============================================================================


class TestMCPServerAuthorizationServer:
    """Tests for authorization_server parameter propagation to OAuth metadata.

    Per RFC 9728 (OAuth Protected Resource Metadata), the authorization_servers
    field tells clients which AS(s) can issue tokens for this resource. When
    MCPServer auto-enables authorization (due to connections), it must pass
    the authorization_server param to AuthorizationConfig so it appears in
    the /.well-known/oauth-protected-resource metadata.
    """

    def test_connections_propagate_authorization_server_to_metadata(self):
        """authorization_server should appear in PRM when connections auto-enable auth."""
        from dedalus_mcp import Connection, MCPServer, SecretKeys

        github = Connection("github", secrets=SecretKeys(token="GITHUB_TOKEN"))
        server = MCPServer(
            name="github-tools",
            connections=[github],
            authorization_server="http://localhost:8443",
        )

        # Server should have auto-enabled authorization
        assert server._authorization_manager is not None
        # The AS URL should be in the config
        assert server._authorization_manager.config.authorization_servers == ["http://localhost:8443"]

    def test_default_authorization_server_used_when_not_specified(self):
        """Default AS (as.dedaluslabs.ai) should be used when not specified."""
        from dedalus_mcp import Connection, MCPServer, SecretKeys

        github = Connection("github", secrets=SecretKeys(token="GITHUB_TOKEN"))
        server = MCPServer(name="github-tools", connections=[github])

        assert server._authorization_manager is not None
        assert server._authorization_manager.config.authorization_servers == ["https://as.dedaluslabs.ai"]

    def test_explicit_authorization_config_overrides_authorization_server(self):
        """Explicit authorization= param should override authorization_server."""
        from dedalus_mcp import Connection, MCPServer, SecretKeys
        from dedalus_mcp.server.authorization import AuthorizationConfig

        github = Connection("github", secrets=SecretKeys(token="GITHUB_TOKEN"))
        explicit_config = AuthorizationConfig(
            enabled=True,
            authorization_servers=["https://custom-as.example.com"],
        )
        server = MCPServer(
            name="github-tools",
            connections=[github],
            authorization=explicit_config,
            authorization_server="http://localhost:8443",  # Should be ignored
        )

        # Explicit config should take precedence
        assert server._authorization_manager.config.authorization_servers == ["https://custom-as.example.com"]

    def test_no_connections_no_auto_auth(self):
        """Without connections, authorization should not be auto-enabled."""
        from dedalus_mcp import MCPServer

        server = MCPServer(name="standalone", authorization_server="http://localhost:8443")

        # No auto-enabled auth without connections
        assert server._authorization_manager is None
