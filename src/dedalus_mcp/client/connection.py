# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""High-level client entrypoint.

`open_connection` wraps transport selection and :class:`~dedalus_mcp.client.MCPClient`
so applications can talk to an MCP server with a single ``async with`` block.

The helper deliberately keeps the surface tiny: callers choose a transport via
``transport=`` (defaulting to streamable HTTP) and receive an
:class:`~dedalus_mcp.client.MCPClient` instance that already negotiated
capabilities. Power users can still reach the underlying transport by using
the lower-level helpers directly.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Mapping
from contextlib import asynccontextmanager
from datetime import timedelta

import httpx

from mcp.client.streamable_http import MCP_PROTOCOL_VERSION, streamable_http_client
from mcp.shared._httpx_utils import create_mcp_http_client
from mcp.types import LATEST_PROTOCOL_VERSION, Implementation

from .core import ClientCapabilitiesConfig, MCPClient
from .transports import lambda_http_client


StreamableHTTPNames = {"streamable-http", "streamable_http", "shttp", "http"}
LambdaHTTPNames = {"lambda-http", "lambda_http"}


def _build_http_client(
    headers: Mapping[str, str] | None,
    timeout: float | timedelta,
    sse_read_timeout: float | timedelta,
    auth: httpx.Auth | None,
) -> httpx.AsyncClient:
    """Build an httpx.AsyncClient with MCP-appropriate settings."""
    # Build headers with MCP protocol version
    base_headers: dict[str, str] = {MCP_PROTOCOL_VERSION: LATEST_PROTOCOL_VERSION}
    if headers:
        base_headers.update(headers)

    # Convert timedelta to float if needed
    timeout_sec = timeout.total_seconds() if isinstance(timeout, timedelta) else timeout
    sse_timeout_sec = sse_read_timeout.total_seconds() if isinstance(sse_read_timeout, timedelta) else sse_read_timeout

    return create_mcp_http_client(
        headers=base_headers,
        timeout=httpx.Timeout(timeout_sec, read=sse_timeout_sec),
        auth=auth,
    )


@asynccontextmanager
async def open_connection(
    url: str,
    *,
    transport: str = "streamable-http",
    headers: Mapping[str, str] | None = None,
    timeout: float | timedelta = 30,
    sse_read_timeout: float | timedelta = 300,
    terminate_on_close: bool = True,
    auth: httpx.Auth | None = None,
    capabilities: ClientCapabilitiesConfig | None = None,
    client_info: Implementation | None = None,
) -> AsyncGenerator[MCPClient, None]:
    """Open an MCP client connection.

    Args:
        url: Fully qualified MCP endpoint (for example, ``"http://127.0.0.1:8000/mcp"``).
        transport: Transport name. Defaults to ``"streamable-http"``; accepts aliases like
            ``"shttp"`` and ``"lambda-http"``.
        headers: Optional HTTP headers to merge into the transport.
        timeout: Total request timeout passed to the underlying transport.
        sse_read_timeout: Streaming read timeout for Server-Sent Events.
        terminate_on_close: Whether to send a transport-level termination request when closing.
        auth: Optional HTTPX authentication handler.
        capabilities: Optional client capability configuration advertised during initialization.
        client_info: Implementation metadata forwarded during the MCP handshake.

    Yields:
        MCPClient: A negotiated MCP client ready for ``send_request`` and other operations.
    """
    selected = transport.lower()

    if selected in StreamableHTTPNames:
        client = _build_http_client(headers, timeout, sse_read_timeout, auth)

        async with client:
            async with (
                streamable_http_client(
                    url,
                    http_client=client,
                    terminate_on_close=terminate_on_close,
                ) as (read_stream, write_stream, get_session_id),
                MCPClient(
                    read_stream,
                    write_stream,
                    capabilities=capabilities,
                    client_info=client_info,
                    get_session_id=get_session_id,
                ) as mcp_client,
            ):
                yield mcp_client
        return

    if selected in LambdaHTTPNames:
        client = _build_http_client(headers, timeout, sse_read_timeout, auth)

        async with client:
            async with (
                lambda_http_client(
                    url,
                    http_client=client,
                    terminate_on_close=terminate_on_close,
                ) as (read_stream, write_stream, get_session_id),
                MCPClient(
                    read_stream,
                    write_stream,
                    capabilities=capabilities,
                    client_info=client_info,
                    get_session_id=get_session_id,
                ) as mcp_client,
            ):
                yield mcp_client
        return

    raise ValueError(f"Unsupported transport '{transport}'")


__all__ = ["open_connection"]
