# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Testing utilities for MCP servers.

Provides helpers to test tools, resources, and prompts without running a full server.
Also includes ConnectionTester for debugging Connection definitions locally.
"""

from __future__ import annotations

import os
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import Token
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .auth import Connection

from .context import _CURRENT_CONTEXT


# --- HTTP Method enum ---


class HttpMethod(str, Enum):
    """HTTP methods for test requests."""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


# --- Test request/response types ---


@dataclass
class TestRequest:
    """Request for ConnectionTester.

    Attributes:
        method: HTTP method (GET, POST, etc.)
        path: URL path (appended to connection's base_url)
        body: JSON body for POST/PUT/PATCH
        headers: Additional headers (merged with auth headers)
        params: Query parameters
    """

    path: str
    method: HttpMethod = HttpMethod.GET
    body: dict[str, Any] | None = None
    headers: dict[str, str] = field(default_factory=dict)
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class TestResponse:
    """Response from ConnectionTester.

    Attributes:
        status: HTTP status code
        body: Parsed JSON body (or None)
        headers: Response headers
    """

    status: int
    body: dict[str, Any] | list[Any] | None
    headers: dict[str, str]

    @property
    def success(self) -> bool:
        """True if status is 2xx."""
        return 200 <= self.status < 300

    def json(self) -> dict[str, Any] | list[Any] | None:
        """Return body as JSON (alias for body property)."""
        return self.body


# --- ConnectionTester ---


class ConnectionTester:
    """Test Connection definitions locally without DAuth.

    Makes real HTTP requests using the Connection's auth configuration.
    Useful for debugging MCP servers before deployment.

    Example:
        >>> from dedalus_mcp.auth import Connection, SecretKeys
        >>> from dedalus_mcp.testing import ConnectionTester
        >>>
        >>> github = Connection(
        ...     name="github",
        ...     secrets=SecretKeys(token="GITHUB_TOKEN"),
        ...     base_url="https://api.github.com",
        ...     auth_header_format="token {api_key}",
        ... )
        >>>
        >>> # From environment variable
        >>> tester = ConnectionTester.from_env(github)
        >>>
        >>> # Or with explicit key
        >>> tester = ConnectionTester(github, api_key="ghp_xxx")
        >>>
        >>> # Test an endpoint
        >>> resp = await tester.request(TestRequest(path="/user"))
        >>> print(resp.success, resp.body)
        >>>
        >>> # Test GraphQL
        >>> resp = await tester.graphql(
        ...     query="query { viewer { login } }",
        ...     endpoint="/graphql",
        ... )
    """

    def __init__(self, connection: Connection, *, api_key: str) -> None:
        """Create a tester for a Connection.

        Args:
            connection: The Connection to test
            api_key: The actual API key/token value
        """
        self._connection = connection
        self._api_key = api_key

    @classmethod
    def from_env(cls, connection: Connection) -> ConnectionTester:
        """Create tester reading the secret from environment.

        Looks up the first secret key defined in the connection's secrets.

        Args:
            connection: The Connection to test

        Returns:
            ConnectionTester with api_key from environment

        Raises:
            ValueError: If the environment variable is not set
        """
        # Get the first secret key's env var name
        if not connection.secrets.entries:
            raise ValueError(f"Connection '{connection.name}' has no secrets defined")

        first_key = next(iter(connection.secrets.entries.values()))
        env_var = first_key.name
        api_key = os.environ.get(env_var)

        if not api_key:
            raise ValueError(f"Environment variable '{env_var}' not set for connection '{connection.name}'")

        return cls(connection, api_key=api_key)

    @property
    def connection(self) -> Connection:
        """The Connection being tested."""
        return self._connection

    @property
    def base_url(self) -> str | None:
        """Base URL for requests."""
        return self._connection.base_url

    def _build_headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        """Build request headers with auth."""
        headers: dict[str, str] = {"Content-Type": "application/json"}

        # Add auth header
        header_name = self._connection.auth_header_name
        header_value = self._connection.auth_header_format.format(api_key=self._api_key)
        headers[header_name] = header_value

        # Merge extra headers
        if extra:
            headers.update(extra)

        return headers

    async def request(self, req: TestRequest) -> TestResponse:
        """Make an HTTP request using the connection's auth.

        Args:
            req: The request to make

        Returns:
            TestResponse with status, body, and headers
        """
        import httpx

        url = f"{self._connection.base_url or ''}{req.path}"
        headers = self._build_headers(req.headers)

        async with httpx.AsyncClient(timeout=self._connection.timeout_ms / 1000) as client:
            response = await client.request(
                method=req.method.value,
                url=url,
                headers=headers,
                params=req.params if req.params else None,
                json=req.body if req.body else None,
            )

            try:
                body = response.json()
            except Exception:
                body = None

            return TestResponse(
                status=response.status_code,
                body=body,
                headers=dict(response.headers),
            )

    async def graphql(
        self,
        query: str,
        *,
        variables: dict[str, Any] | None = None,
        operation_name: str | None = None,
        endpoint: str = "/graphql",
    ) -> TestResponse:
        """Make a GraphQL request.

        GraphQL is just HTTP POST with a JSON body containing query/variables.

        Args:
            query: The GraphQL query string
            variables: Optional query variables
            operation_name: Optional operation name (for multi-operation documents)
            endpoint: GraphQL endpoint path (default: /graphql)

        Returns:
            TestResponse with GraphQL result
        """
        body: dict[str, Any] = {"query": query}
        if variables:
            body["variables"] = variables
        if operation_name:
            body["operationName"] = operation_name

        return await self.request(
            TestRequest(
                method=HttpMethod.POST,
                path=endpoint,
                body=body,
            )
        )

    async def ping(self, path: str = "/") -> bool:
        """Check if the connection is working.

        Args:
            path: Endpoint to ping (default: /)

        Returns:
            True if request succeeds (2xx), False otherwise
        """
        try:
            resp = await self.request(TestRequest(path=path))
            return resp.success
        except Exception:
            return False


@dataclass
class MockContext:
    """Mock context for testing tools outside of request handlers.

    Captures log messages and provides no-op implementations for progress.

    Usage:
        with mock_context() as ctx:
            result = await my_tool.impl()
            assert ctx.captured_logs[0][1] == "expected message"
    """

    _request_id: str = "test-request-1"
    captured_logs: list[tuple[str, str, dict[str, Any] | None]] = field(default_factory=list)

    @property
    def request_id(self) -> str:
        return self._request_id

    @property
    def session_id(self) -> str | None:
        return None

    @property
    def progress_token(self) -> None:
        return None

    @property
    def auth_context(self) -> None:
        return None

    @property
    def server(self) -> None:
        return None

    @property
    def resolver(self) -> None:
        return None

    async def log(
        self, level: str, message: str, *, logger: str | None = None, data: Mapping[str, Any] | None = None
    ) -> None:
        self.captured_logs.append((level, message, dict(data) if data else None))

    async def debug(self, message: str, *, logger: str | None = None, data: Mapping[str, Any] | None = None) -> None:
        await self.log("debug", message, logger=logger, data=data)

    async def info(self, message: str, *, logger: str | None = None, data: Mapping[str, Any] | None = None) -> None:
        await self.log("info", message, logger=logger, data=data)

    async def warning(self, message: str, *, logger: str | None = None, data: Mapping[str, Any] | None = None) -> None:
        await self.log("warning", message, logger=logger, data=data)

    async def error(self, message: str, *, logger: str | None = None, data: Mapping[str, Any] | None = None) -> None:
        await self.log("error", message, logger=logger, data=data)

    async def report_progress(self, progress: float, *, total: float | None = None, message: str | None = None) -> None:
        # No-op in mock context
        pass


@contextmanager
def mock_context(*, request_id: str = "test-request-1") -> Iterator[MockContext]:
    """Context manager that provides a mock context for testing.

    Makes get_context() work outside of MCP request handlers.

    Args:
        request_id: Custom request ID for the mock context.

    Example:
        from dedalus_mcp import get_context
        from dedalus_mcp.testing import mock_context

        @tool(description="Log something")
        async def my_tool() -> str:
            ctx = get_context()
            await ctx.info("hello")
            return "done"

        # Test without running a server
        with mock_context() as ctx:
            result = await my_tool.impl()
            assert ctx.captured_logs[0][1] == "hello"
    """
    ctx = MockContext(_request_id=request_id)
    token: Token[Any] = _CURRENT_CONTEXT.set(ctx)  # type: ignore[arg-type]
    try:
        yield ctx
    finally:
        _CURRENT_CONTEXT.reset(token)


__all__ = [
    "ConnectionTester",
    "HttpMethod",
    "MockContext",
    "TestRequest",
    "TestResponse",
    "mock_context",
]
