# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Example: Using typed connectors with define() and EnvironmentCredentialLoader.

This demonstrates the typed connector pattern for framework developers building
drivers, vault integrations, or SDK clients that need full Pydantic validation.

For simple HTTP REST API dispatch (GitHub, Supabase), use the Connection pattern
shown in examples/north_star.py instead.

When to use typed connectors:
- Building database drivers (PostgreSQL, MongoDB, Redis)
- SDK client integrations (OpenAI, Anthropic SDKs)
- Vault-based credential management (production deployments)
- Need compile-time type safety and runtime validation

When NOT to use typed connectors:
- Simple REST API calls (use Connection + ctx.dispatch instead)
- Rapid prototyping (Connection is simpler)
- No need for Pydantic models (Connection uses dicts)
"""

import asyncio
import os

from dedalus_mcp.server.connectors import (
    Credentials,
    EnvironmentCredentialLoader,
    EnvironmentCredentials,
    define,
)


# =============================================================================
# Example 1: Basic Typed Connector
# =============================================================================


def example_basic_connector():
    """Define a basic typed connector for an HTTP API."""

    # Define the connector schema
    HttpApiConn = define(
        kind="http-api",
        params={"base_url": str},
        auth=["service_credential", "user_token"],
        description="Generic HTTP API with service or user credentials",
    )

    # Create environment credential loader
    loader = EnvironmentCredentialLoader(
        connector=HttpApiConn,
        variants={
            "service_credential": EnvironmentCredentials(
                config=Credentials(base_url="API_BASE_URL"),
                secrets=Credentials(secret="API_SECRET_KEY"),
            ),
            "user_token": EnvironmentCredentials(
                config=Credentials(base_url="API_BASE_URL"),
                secrets=Credentials(token="USER_ACCESS_TOKEN"),
            ),
        },
    )

    # Set environment variables
    os.environ["API_BASE_URL"] = "https://api.example.com"
    os.environ["API_SECRET_KEY"] = "secret_abc123"

    # Load credentials
    resolved = loader.load("service_credential")

    # Access typed models
    print(f"Connection Handle: {resolved.handle.id}")
    print(f"Config: {resolved.config.model_dump()}")
    print(f"Auth: {resolved.auth.model_dump()}")

    # resolved.config is a Pydantic model with:
    #   base_url: str = "https://api.example.com"
    # resolved.auth is a Pydantic model with:
    #   type: Literal["service_credential"]
    #   secret: str = "secret_abc123"


# =============================================================================
# Example 2: Database Connector with Multiple Parameters
# =============================================================================


def example_database_connector():
    """Define a PostgreSQL connector with typed parameters."""

    PostgresConn = define(
        kind="postgres",
        params={
            "host": str,
            "port": int,
            "database": str,
            "ssl_mode": str,
        },
        auth=["password", "iam"],
        description="PostgreSQL database connection",
    )

    loader = EnvironmentCredentialLoader(
        connector=PostgresConn,
        variants={
            "password": EnvironmentCredentials(
                config=Credentials(
                    host="POSTGRES_HOST",
                    port="POSTGRES_PORT",
                    database="POSTGRES_DB",
                    ssl_mode="POSTGRES_SSL_MODE",
                ),
                secrets=Credentials(
                    username="POSTGRES_USER",
                    password="POSTGRES_PASSWORD",
                ),
            ),
        },
    )

    # Set environment
    os.environ.update(
        {
            "POSTGRES_HOST": "db.example.com",
            "POSTGRES_PORT": "5432",
            "POSTGRES_DB": "myapp",
            "POSTGRES_SSL_MODE": "require",
            "POSTGRES_USER": "admin",
            "POSTGRES_PASSWORD": "secure_pass",
        }
    )

    # Load and validate
    resolved = loader.load("password")

    # Config model has typed fields:
    assert resolved.config.host == "db.example.com"
    assert resolved.config.port == 5432  # Automatically cast to int
    assert resolved.config.database == "myapp"
    assert resolved.config.ssl_mode == "require"

    # Auth model has secrets + type discriminator:
    assert resolved.auth.type == "password"
    assert resolved.auth.username == "admin"
    assert resolved.auth.password == "secure_pass"

    print("PostgreSQL connector validated successfully")


# =============================================================================
# Example 3: Using with a Driver
# =============================================================================


class MockPostgresDriver:
    """Example driver that creates a database client."""

    async def create_client(self, config, auth):
        """Create client from typed config and auth models.

        Args:
            config: Pydantic model with host, port, database, ssl_mode
            auth: Pydantic model with username, password, type
        """
        # In real implementation, would use asyncpg.connect()
        connection_string = (
            f"postgresql://{auth.username}:{auth.password}"
            f"@{config.host}:{config.port}/{config.database}"
            f"?sslmode={config.ssl_mode}"
        )
        print(f"Would connect to: {connection_string}")
        return {"connected": True, "db": config.database}


async def example_with_driver():
    """Use typed connector with a driver."""

    PostgresConn = define(
        kind="postgres",
        params={"host": str, "port": int, "database": str, "ssl_mode": str},
        auth=["password"],
    )

    loader = EnvironmentCredentialLoader(
        connector=PostgresConn,
        variants={
            "password": EnvironmentCredentials(
                config=Credentials(
                    host="POSTGRES_HOST",
                    port="POSTGRES_PORT",
                    database="POSTGRES_DB",
                    ssl_mode="POSTGRES_SSL_MODE",
                ),
                secrets=Credentials(username="POSTGRES_USER", password="POSTGRES_PASSWORD"),
            ),
        },
    )

    os.environ.update(
        {
            "POSTGRES_HOST": "localhost",
            "POSTGRES_PORT": "5432",
            "POSTGRES_DB": "testdb",
            "POSTGRES_SSL_MODE": "disable",
            "POSTGRES_USER": "postgres",
            "POSTGRES_PASSWORD": "password",
        }
    )

    # Load credentials
    resolved = loader.load("password")

    # Create driver instance
    driver = MockPostgresDriver()

    # Build client with typed config and auth
    client = await driver.create_client(resolved.config, resolved.auth)
    print(f"Client created: {client}")


# =============================================================================
# Example 4: Optional Fields and Defaults
# =============================================================================


def example_optional_fields():
    """Show optional fields and defaults in connectors."""
    from dedalus_mcp.server.connectors import Binding

    OpenAIConn = define(
        kind="openai",
        params={"base_url": str, "model": str},
        auth=["api_key"],
    )

    loader = EnvironmentCredentialLoader(
        connector=OpenAIConn,
        variants={
            "api_key": EnvironmentCredentials(
                config=Credentials(
                    base_url=Binding("OPENAI_BASE_URL", default="https://api.openai.com/v1"),
                    model=Binding("OPENAI_MODEL", default="gpt-4"),
                ),
                secrets=Credentials(
                    api_key="OPENAI_API_KEY",
                    org_id=Binding("OPENAI_ORG_ID", optional=True),
                ),
            ),
        },
    )

    # Only set required env vars
    os.environ["OPENAI_API_KEY"] = "sk-test123"
    # OPENAI_BASE_URL and OPENAI_MODEL will use defaults
    # OPENAI_ORG_ID is optional, can be missing

    resolved = loader.load("api_key")

    assert resolved.config.base_url == "https://api.openai.com/v1"
    assert resolved.config.model == "gpt-4"
    assert resolved.auth.api_key == "sk-test123"
    # org_id will be None since it's optional and not set

    print("Optional fields example passed")


# =============================================================================
# Comparison: Connection vs define()
# =============================================================================


def comparison_connection_vs_define():
    """Show when to use Connection (simple) vs define() (typed)."""

    # -------------------------------------------------------------------------
    # Pattern A: Connection (for HTTP dispatch)
    # -------------------------------------------------------------------------
    from dedalus_mcp import Connection, Credentials, HttpMethod, HttpRequest, MCPServer, get_context, tool

    github = Connection(
        "github",
        credentials=Credentials(token="GITHUB_TOKEN"),
        base_url="https://api.github.com",
    )

    server = MCPServer(name="github-tools", connections=[github])

    @tool(description="List repos")
    async def list_repos():
        ctx = get_context()
        response = await ctx.dispatch(
            "github",
            HttpRequest(method=HttpMethod.GET, path="/user/repos"),
        )
        if response.success:
            return response.response.body
        return []

    # Simple, no ceremony, perfect for REST APIs

    # -------------------------------------------------------------------------
    # Pattern B: define() (for typed drivers)
    # -------------------------------------------------------------------------
    from dedalus_mcp.server.connectors import (
        EnvironmentCredentialLoader,
        EnvironmentCredentials,
        define,
    )

    PostgresConn = define(
        kind="postgres",
        params={"host": str, "port": int, "database": str},
        auth=["password"],
    )

    loader = EnvironmentCredentialLoader(
        connector=PostgresConn,
        variants={
            "password": EnvironmentCredentials(
                config=Credentials(host="POSTGRES_HOST", port="POSTGRES_PORT", database="POSTGRES_DB"),
                secrets=Credentials(username="POSTGRES_USER", password="POSTGRES_PASSWORD"),
            ),
        },
    )

    # At runtime:
    # resolved = loader.load("password")
    # client = await postgres_driver.create_client(resolved.config, resolved.auth)
    # result = await client.execute("SELECT * FROM users")

    # More ceremony, but gives you typed Pydantic models and driver integration

    print("Use Connection for HTTP APIs, define() for drivers/SDKs")


# =============================================================================
# Main
# =============================================================================


async def main():
    """Run all examples."""
    print("\n=== Example 1: Basic Typed Connector ===")
    example_basic_connector()

    print("\n=== Example 2: Database Connector ===")
    example_database_connector()

    print("\n=== Example 3: Using with Driver ===")
    await example_with_driver()

    print("\n=== Example 4: Optional Fields ===")
    example_optional_fields()

    print("\n=== Comparison: Connection vs define() ===")
    comparison_connection_vs_define()


if __name__ == "__main__":
    asyncio.run(main())
