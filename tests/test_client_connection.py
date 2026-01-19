# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

from __future__ import annotations

import socket

import anyio
import httpx
import pytest

from dedalus_mcp import MCPServer, tool
from dedalus_mcp.types.messages import ClientRequest
from dedalus_mcp.types.server.tools import CallToolRequest, CallToolRequestParams, CallToolResult
from dedalus_mcp.client import open_connection, MCPClient
from dedalus_mcp.versioning import V_2024_11_05


HTTP_OK = 200
HTTP_BAD_REQUEST = 400
JSONRPC_INVALID_REQUEST = -32600


async def _wait_for_port(host: str, port: int, *, timeout: float = 5.0) -> None:
    with anyio.fail_after(timeout):
        while True:
            try:
                with socket.create_connection((host, port), timeout=0.1):
                    return
            except OSError:
                await anyio.sleep(0.05)


@pytest.mark.anyio
async def test_open_connection_streamable_http(unused_tcp_port: int) -> None:
    server = MCPServer("connection-test")

    with server.binding():

        @tool()
        def add(a: int, b: int) -> int:
            return a + b

    host = "127.0.0.1"
    port = unused_tcp_port

    async def run_server() -> None:
        await server.serve(transport="streamable-http", host=host, port=port)

    async with anyio.create_task_group() as tg:
        tg.start_soon(run_server)
        await _wait_for_port(host, port)

        try:
            async with open_connection(f"http://{host}:{port}/mcp") as client:
                result = await client.send_request(
                    ClientRequest(
                        CallToolRequest(params=CallToolRequestParams(name="add", arguments={"a": 3, "b": 4}))
                    ),
                    CallToolResult,
                )

                assert not result.isError
                assert result.content
                assert result.content[0].text == "7"
                if result.structuredContent is not None:
                    assert result.structuredContent == {"result": 7}
                assert client.session is not None
        finally:
            await server.shutdown()


@pytest.mark.anyio
async def test_open_connection_unknown_transport() -> None:
    with pytest.raises(ValueError, match="Unsupported transport"):
        async with open_connection("whatever://", transport="bogus"):
            pass


@pytest.mark.anyio
async def test_streamable_http_allows_preinitialize_get(unused_tcp_port: int) -> None:
    server = MCPServer("preinit-get")

    host = "127.0.0.1"
    port = unused_tcp_port

    async def run_server() -> None:
        await server.serve(transport="streamable-http", host=host, port=port)

    async with anyio.create_task_group() as tg:
        tg.start_soon(run_server)
        await _wait_for_port(host, port)

        try:
            version = str(V_2024_11_05)
            base_url = f"http://{host}:{port}/mcp"

            async with httpx.AsyncClient(timeout=2.0) as client:
                initialize_payload = {
                    "jsonrpc": "2.0",
                    "id": "init-1",
                    "method": "initialize",
                    "params": {
                        "protocolVersion": version,
                        "capabilities": {},
                        "clientInfo": {"name": "test-client", "version": "0.0.0"},
                    },
                }

                post_headers = {
                    "MCP-Protocol-Version": version,
                    "Accept": "application/json, text/event-stream",
                    "Content-Type": "application/json",
                }

                async with client.stream(
                    "POST", base_url, headers=post_headers, json=initialize_payload
                ) as init_response:
                    assert init_response.status_code == HTTP_OK
                    session_id = init_response.headers.get("Mcp-Session-Id")
                    assert session_id

                get_headers = {
                    "MCP-Protocol-Version": version,
                    "Mcp-Session-Id": session_id,
                    "Accept": "text/event-stream",
                }

                async with client.stream("GET", base_url, headers=get_headers) as response:
                    assert response.status_code == HTTP_OK
        finally:
            await server.shutdown()


@pytest.mark.anyio
async def test_streamable_http_stateless_allows_preinitialize_get(unused_tcp_port: int) -> None:
    server = MCPServer("stateless", streamable_http_stateless=True)

    host = "127.0.0.1"
    port = unused_tcp_port

    async def run_server() -> None:
        await server.serve(transport="streamable-http", host=host, port=port)

    async with anyio.create_task_group() as tg:
        tg.start_soon(run_server)
        await _wait_for_port(host, port)

        try:
            headers = {"MCP-Protocol-Version": str(V_2024_11_05), "Accept": "text/event-stream"}

            async with (
                httpx.AsyncClient(timeout=2.0) as client,
                client.stream("GET", f"http://{host}:{port}/mcp", headers=headers) as response,
            ):
                assert response.status_code == HTTP_OK
        finally:
            await server.shutdown()


@pytest.mark.anyio
async def test_streamable_http_preinitialize_get_requires_session(unused_tcp_port: int) -> None:
    server = MCPServer("stateful-get")

    host = "127.0.0.1"
    port = unused_tcp_port

    async def run_server() -> None:
        await server.serve(transport="streamable-http", host=host, port=port)

    async with anyio.create_task_group() as tg:
        tg.start_soon(run_server)
        await _wait_for_port(host, port)

        try:
            headers = {"MCP-Protocol-Version": str(V_2024_11_05), "Accept": "text/event-stream"}

            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(f"http://{host}:{port}/mcp", headers=headers)
                assert response.status_code == HTTP_BAD_REQUEST
                payload = response.json()
                error = payload.get("error", {})
                assert error.get("code") == JSONRPC_INVALID_REQUEST
                message = error.get("message", "").lower()
                assert "missing" in message
                assert "session" in message
        finally:
            await server.shutdown()


# ---------------------------------------------------------------------
# MCPClient.connect() Integration Tests
# ---------------------------------------------------------------------


@pytest.mark.anyio
async def test_mcpclient_connect_streamable_http(unused_tcp_port: int) -> None:
    """MCPClient.connect() should work with streamable-http transport."""
    server = MCPServer("connect-test")

    with server.binding():

        @tool()
        def multiply(a: int, b: int) -> int:
            return a * b

    host = "127.0.0.1"
    port = unused_tcp_port

    async def run_server() -> None:
        await server.serve(transport="streamable-http", host=host, port=port)

    async with anyio.create_task_group() as tg:
        tg.start_soon(run_server)
        await _wait_for_port(host, port)

        try:
            # Use the new connect() API
            client = await MCPClient.connect(f"http://{host}:{port}/mcp")

            try:
                # Should be initialized
                assert client.initialize_result is not None
                assert client.initialize_result.serverInfo.name == "connect-test"

                # Should be able to call tools
                result = await client.send_request(
                    ClientRequest(
                        CallToolRequest(params=CallToolRequestParams(name="multiply", arguments={"a": 5, "b": 6}))
                    ),
                    CallToolResult,
                )

                assert not result.isError
                assert result.content
                assert result.content[0].text == "30"
            finally:
                await client.close()
        finally:
            await server.shutdown()


@pytest.mark.anyio
async def test_mcpclient_connect_context_manager(unused_tcp_port: int) -> None:
    """MCPClient.connect() should work with async with."""
    server = MCPServer("ctx-test")

    with server.binding():

        @tool()
        def greet(name: str) -> str:
            return f"Hello, {name}!"

    host = "127.0.0.1"
    port = unused_tcp_port

    async def run_server() -> None:
        await server.serve(transport="streamable-http", host=host, port=port)

    async with anyio.create_task_group() as tg:
        tg.start_soon(run_server)
        await _wait_for_port(host, port)

        try:
            # Use connect() with context manager
            async with await MCPClient.connect(f"http://{host}:{port}/mcp") as client:
                result = await client.send_request(
                    ClientRequest(
                        CallToolRequest(params=CallToolRequestParams(name="greet", arguments={"name": "World"}))
                    ),
                    CallToolResult,
                )

                assert not result.isError
                assert result.content
                assert result.content[0].text == "Hello, World!"

            # Client should be closed after exiting context
            assert client._closed is True
        finally:
            await server.shutdown()


@pytest.mark.anyio
async def test_mcpclient_connect_unknown_transport() -> None:
    """MCPClient.connect() should raise for unknown transport."""
    with pytest.raises(ValueError, match="Unsupported transport"):
        await MCPClient.connect("http://localhost:8000/mcp", transport="bogus")
