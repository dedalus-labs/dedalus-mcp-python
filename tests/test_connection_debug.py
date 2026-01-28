# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Tests for connection debugging utilities.

These utilities help developers test their Connection definitions locally
without needing the full DAuth infrastructure.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from dedalus_mcp.auth import Connection, SecretKeys
from dedalus_mcp.testing import ConnectionTester, HttpMethod, TestRequest, TestResponse


# --- Fixtures ---


@pytest.fixture
def github_connection() -> Connection:
    """Sample GitHub connection for testing."""
    return Connection(
        name="github",
        secrets=SecretKeys(token="GITHUB_TOKEN"),
        base_url="https://api.github.com",
        auth_header_format="token {api_key}",
    )


@pytest.fixture
def supabase_connection() -> Connection:
    """Sample Supabase connection with custom header."""
    return Connection(
        name="supabase",
        secrets=SecretKeys(key="SUPABASE_KEY"),
        base_url="https://xyz.supabase.co/rest/v1",
        auth_header_name="apikey",
        auth_header_format="{api_key}",
    )


@pytest.fixture
def graphql_connection() -> Connection:
    """Sample GraphQL API connection."""
    return Connection(
        name="graphql-api",
        secrets=SecretKeys(token="GRAPHQL_TOKEN"),
        base_url="https://api.example.com",
        auth_header_format="Bearer {api_key}",
    )


# --- TestRequest / TestResponse ---


def test_test_request_defaults():
    """TestRequest has sensible defaults."""
    req = TestRequest(path="/users")
    assert req.method == HttpMethod.GET
    assert req.path == "/users"
    assert req.body is None
    assert req.headers == {}
    assert req.params == {}


def test_test_request_post_with_body():
    """TestRequest can have POST body."""
    req = TestRequest(method=HttpMethod.POST, path="/users", body={"name": "test"})
    assert req.method == HttpMethod.POST
    assert req.body == {"name": "test"}


def test_test_response_success():
    """TestResponse captures success state."""
    resp = TestResponse(status=200, body={"id": 1}, headers={"content-type": "application/json"})
    assert resp.success
    assert resp.status == 200
    assert resp.body == {"id": 1}


def test_test_response_failure():
    """TestResponse captures failure state."""
    resp = TestResponse(status=401, body={"error": "unauthorized"}, headers={})
    assert not resp.success
    assert resp.status == 401


def test_test_response_json_method():
    """TestResponse.json() returns body as dict."""
    resp = TestResponse(status=200, body={"key": "value"}, headers={})
    assert resp.json() == {"key": "value"}


# --- ConnectionTester ---


def test_connection_tester_init(github_connection: Connection):
    """ConnectionTester initializes with connection and secret."""
    tester = ConnectionTester(github_connection, api_key="ghp_test123")
    assert tester.connection is github_connection
    assert tester.base_url == "https://api.github.com"


def test_connection_tester_builds_headers(github_connection: Connection):
    """ConnectionTester builds auth headers correctly."""
    tester = ConnectionTester(github_connection, api_key="ghp_test123")
    headers = tester._build_headers()
    assert headers["Authorization"] == "token ghp_test123"


def test_connection_tester_custom_header(supabase_connection: Connection):
    """ConnectionTester handles custom header names."""
    tester = ConnectionTester(supabase_connection, api_key="sb_key123")
    headers = tester._build_headers()
    assert headers["apikey"] == "sb_key123"
    assert "Authorization" not in headers


@pytest.mark.anyio
async def test_connection_tester_get(github_connection: Connection):
    """ConnectionTester.request() makes GET requests."""
    tester = ConnectionTester(github_connection, api_key="ghp_test123")

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = lambda: {"login": "testuser"}  # Not async - httpx.Response.json() is sync
    mock_response.headers = {"content-type": "application/json"}

    with patch("httpx.AsyncClient.request", return_value=mock_response) as mock_req:
        resp = await tester.request(TestRequest(path="/user"))

        mock_req.assert_called_once()
        call_kwargs = mock_req.call_args.kwargs
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["url"] == "https://api.github.com/user"
        assert resp.success
        assert resp.body == {"login": "testuser"}


@pytest.mark.anyio
async def test_connection_tester_post_json(github_connection: Connection):
    """ConnectionTester.request() sends JSON body for POST."""
    tester = ConnectionTester(github_connection, api_key="ghp_test123")

    mock_response = AsyncMock()
    mock_response.status_code = 201
    mock_response.json = lambda: {"id": 123}
    mock_response.headers = {}

    with patch("httpx.AsyncClient.request", return_value=mock_response) as mock_req:
        resp = await tester.request(TestRequest(method=HttpMethod.POST, path="/repos", body={"name": "new-repo"}))

        call_kwargs = mock_req.call_args.kwargs
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["json"] == {"name": "new-repo"}
        assert resp.status == 201


@pytest.mark.anyio
async def test_connection_tester_with_params(github_connection: Connection):
    """ConnectionTester.request() passes query params."""
    tester = ConnectionTester(github_connection, api_key="ghp_test123")

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = lambda: []
    mock_response.headers = {}

    with patch("httpx.AsyncClient.request", return_value=mock_response) as mock_req:
        resp = await tester.request(TestRequest(path="/repos", params={"per_page": 10}))

        call_kwargs = mock_req.call_args.kwargs
        assert call_kwargs["params"] == {"per_page": 10}


# --- GraphQL support ---


@pytest.mark.anyio
async def test_connection_tester_graphql(graphql_connection: Connection):
    """ConnectionTester.graphql() sends GraphQL queries."""
    tester = ConnectionTester(graphql_connection, api_key="gql_token123")

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = lambda: {"data": {"user": {"id": "123", "name": "Test"}}}
    mock_response.headers = {}

    with patch("httpx.AsyncClient.request", return_value=mock_response) as mock_req:
        resp = await tester.graphql(
            query="query($id: ID!) { user(id: $id) { id name } }",
            variables={"id": "123"},
            endpoint="/graphql",
        )

        call_kwargs = mock_req.call_args.kwargs
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["url"] == "https://api.example.com/graphql"
        assert call_kwargs["json"]["query"] == "query($id: ID!) { user(id: $id) { id name } }"
        assert call_kwargs["json"]["variables"] == {"id": "123"}
        assert resp.success
        assert resp.body["data"]["user"]["name"] == "Test"


@pytest.mark.anyio
async def test_connection_tester_graphql_with_operation_name(graphql_connection: Connection):
    """ConnectionTester.graphql() supports operation names."""
    tester = ConnectionTester(graphql_connection, api_key="gql_token123")

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = lambda: {"data": {}}
    mock_response.headers = {}

    with patch("httpx.AsyncClient.request", return_value=mock_response) as mock_req:
        await tester.graphql(
            query="query GetUser { user { id } }",
            operation_name="GetUser",
        )

        call_kwargs = mock_req.call_args.kwargs
        assert call_kwargs["json"]["operationName"] == "GetUser"


# --- Health check / ping ---


@pytest.mark.anyio
async def test_connection_tester_ping_success(github_connection: Connection):
    """ConnectionTester.ping() returns True on success."""
    tester = ConnectionTester(github_connection, api_key="ghp_test123")

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = lambda: {}
    mock_response.headers = {}

    with patch("httpx.AsyncClient.request", return_value=mock_response):
        result = await tester.ping("/")
        assert result is True


@pytest.mark.anyio
async def test_connection_tester_ping_failure(github_connection: Connection):
    """ConnectionTester.ping() returns False on auth failure."""
    tester = ConnectionTester(github_connection, api_key="bad_key")

    mock_response = AsyncMock()
    mock_response.status_code = 401
    mock_response.json = lambda: {"message": "Bad credentials"}
    mock_response.headers = {}

    with patch("httpx.AsyncClient.request", return_value=mock_response):
        result = await tester.ping("/")
        assert result is False


# --- Convenience factory ---


def test_connection_tester_from_env(github_connection: Connection, monkeypatch: pytest.MonkeyPatch):
    """ConnectionTester.from_env() reads secret from environment."""
    monkeypatch.setenv("GITHUB_TOKEN", "env_token_123")

    tester = ConnectionTester.from_env(github_connection)
    headers = tester._build_headers()
    assert headers["Authorization"] == "token env_token_123"


def test_connection_tester_from_env_missing(github_connection: Connection, monkeypatch: pytest.MonkeyPatch):
    """ConnectionTester.from_env() raises if env var missing."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    with pytest.raises(ValueError, match="GITHUB_TOKEN"):
        ConnectionTester.from_env(github_connection)
