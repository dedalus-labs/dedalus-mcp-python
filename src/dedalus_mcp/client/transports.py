# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""HTTP transport helpers for :mod:`dedalus_mcp.client`.

This module provides variants of the streamable HTTP transport described in the
Model Context Protocol specification. ``lambda_http_client`` mirrors
the reference SDK implementation but deliberately avoids registering a
server-push GET stream so that it works with stateless environments such as AWS
Lambda. The behavior aligns with the "POST-only" pattern noted in the spec's
server guidance.
"""

from __future__ import annotations

import contextlib
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import anyio
import httpx
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream

from mcp.client.streamable_http import GetSessionIdCallback, StreamableHTTPTransport
from mcp.shared._httpx_utils import create_mcp_http_client
from mcp.shared.message import SessionMessage


@asynccontextmanager
async def lambda_http_client(
    url: str,
    *,
    http_client: httpx.AsyncClient | None = None,
    terminate_on_close: bool = True,
) -> AsyncGenerator[
    tuple[
        MemoryObjectReceiveStream[SessionMessage | Exception],
        MemoryObjectSendStream[SessionMessage],
        GetSessionIdCallback,
    ],
    None,
]:
    """Create a streamable HTTP transport without the persistent GET stream.

    The Model Context Protocol allows streamable HTTP transports to keep a
    server-push channel open, but serverless hosts like AWS Lambda cannot
    maintain such long-lived connections. ``lambda_http_client`` mirrors the
    reference SDK's ``streamable_http_client`` implementation while replacing
    the ``start_get_stream`` callback with a no-op. This keeps each JSON-RPC
    request self-contained.

    Args:
        url: The MCP server endpoint URL.
        http_client: Optional pre-configured httpx.AsyncClient. If None, a default
            client with recommended MCP timeouts will be created. To configure headers,
            authentication, or other HTTP settings, create an httpx.AsyncClient
            and pass it here.
        terminate_on_close: If True, send a DELETE request to terminate the session
            when the context exits.

    Yields:
        Tuple of ``(read_stream, write_stream, get_session_id)`` compatible with
        :class:`mcp.client.session.ClientSession`.
    """
    read_writer, read_stream = anyio.create_memory_object_stream[SessionMessage | Exception](0)
    write_stream, write_reader = anyio.create_memory_object_stream[SessionMessage](0)

    # Determine if we need to create and manage the client
    client_provided = http_client is not None
    client = http_client if client_provided else create_mcp_http_client()

    transport = StreamableHTTPTransport(url)

    async with anyio.create_task_group() as tg:
        try:
            async with contextlib.AsyncExitStack() as stack:
                # Only manage client lifecycle if we created it
                if not client_provided:
                    await stack.enter_async_context(client)

                def _noop_start_get_stream() -> None:
                    """Lambda-safe placeholder that intentionally avoids SSE."""

                tg.start_soon(
                    transport.post_writer, client, write_reader, read_writer, write_stream, _noop_start_get_stream, tg
                )

                try:
                    yield read_stream, write_stream, transport.get_session_id
                finally:
                    if transport.session_id and terminate_on_close:
                        await transport.terminate_session(client)
                    tg.cancel_scope.cancel()
        finally:
            await read_writer.aclose()
            await write_stream.aclose()
