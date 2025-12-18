# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""High-level MCP client wrapper built on the reference SDK.

Implements MCP client behavior per the specification.

`MCPClient` manages the initialization handshake, capability negotiation,
optional client-side features (sampling, elicitation, roots, logging), and
exposes convenience helpers for protocol operations.  It stays thin by
leveraging the official `ClientSession` class while providing ergonomic hooks
and safety checks for host applications.

The client supports both script-style usage (with explicit `close()`) and
context manager patterns:

    # Script-style (recommended for simple scripts)
    client = await MCPClient.connect("http://localhost:8000/mcp")
    tools = await client.list_tools()
    await client.close()

    # Context manager (recommended for guaranteed cleanup)
    async with await MCPClient.connect("http://localhost:8000/mcp") as client:
        tools = await client.list_tools()
"""

from __future__ import annotations

import warnings
import weakref
from collections.abc import Awaitable, Callable, Iterable
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypeVar

from anyio import Lock
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
import httpx

from mcp.client.session import ClientSession

from .errors import MCPConnectionError, SessionExpiredError
from .error_handling import (
    extract_http_error,
    extract_network_error,
    http_error_to_mcp_error,
    network_error_to_mcp_error,
)

from ..types.client.elicitation import ElicitRequestParams, ElicitResult
from ..types.client.roots import ListRootsResult, Root
from ..types.client.sampling import CreateMessageRequestParams, CreateMessageResult
from ..types.lifecycle import InitializeResult
from ..types.messages import ClientNotification, ClientRequest, ClientResult
from ..types.server.logging import LoggingMessageNotificationParams
from ..types.server.prompts import GetPromptResult, ListPromptsResult
from ..types.server.resources import ListResourcesResult, ReadResourceResult
from ..types.server.tools import CallToolResult, ListToolsResult
from ..types.shared.base import EmptyResult, ErrorData
from ..types.shared.capabilities import Implementation
from ..types.shared.primitives import RequestId
from ..types.utilities.cancellation import CancelledNotification, CancelledNotificationParams
from ..types.utilities.ping import PingRequest
from ..utils.coro import maybe_await_with_args

if TYPE_CHECKING:
    pass


SamplingHandler = Callable[
    [Any, CreateMessageRequestParams], Awaitable[CreateMessageResult | ErrorData] | CreateMessageResult | ErrorData
]
ElicitationHandler = Callable[
    [Any, ElicitRequestParams], Awaitable[ElicitResult | ErrorData] | ElicitResult | ErrorData
]
LoggingHandler = Callable[[LoggingMessageNotificationParams], Awaitable[None] | None]

T_RequestResult = TypeVar("T_RequestResult")


@dataclass(slots=True)
class ClientCapabilitiesConfig:
    """Optional capability handlers for the client."""

    sampling: SamplingHandler | None = None
    elicitation: ElicitationHandler | None = None
    logging: LoggingHandler | None = None
    initial_roots: Iterable[Root | dict[str, Any]] | None = None
    enable_roots: bool = False


class MCPClient:
    """Lifecycle-aware wrapper around :class:`mcp.client.session.ClientSession`.

    Supports both script-style usage and context managers:

        # Script-style
        client = await MCPClient.connect("http://localhost:8000/mcp")
        tools = await client.list_tools()
        await client.close()

        # Context manager
        async with await MCPClient.connect("http://localhost:8000/mcp") as client:
            tools = await client.list_tools()

    Parameters correspond to the optional client features described in
    the MCP specification. Hosts can provide handlers for sampling, elicitation,
    logging, and root discovery to negotiate those capabilities during initialization.
    """

    def __init__(
        self,
        read_stream: MemoryObjectReceiveStream[Any],
        write_stream: MemoryObjectSendStream[Any],
        *,
        capabilities: ClientCapabilitiesConfig | None = None,
        client_info: Implementation | None = None,
        get_session_id: Callable[[], str | None] | None = None,
        _exit_stack: AsyncExitStack | None = None,
    ) -> None:
        self._read_stream = read_stream
        self._write_stream = write_stream
        self._client_info = client_info
        self._get_session_id = get_session_id
        self._exit_stack = _exit_stack  # Manages transport lifecycle for connect() API

        self._config = capabilities or ClientCapabilitiesConfig()
        self._supports_roots = self._config.enable_roots or self._config.initial_roots is not None

        initial_roots = list(self._config.initial_roots or []) if self._supports_roots else []
        self._root_lock = Lock()
        self._roots_version = 0
        self._roots: list[Root] = [self._normalize_root(root) for root in initial_roots]

        self._session: ClientSession | None = None
        self.initialize_result: InitializeResult | None = None
        self._closed: bool = False

        # Safety net: warn if close() wasn't called
        self._finalizer = weakref.finalize(self, self._warn_unclosed, id(self))

    @staticmethod
    def _warn_unclosed(client_id: int) -> None:
        """Called by finalizer if client wasn't properly closed."""
        warnings.warn(
            f"MCPClient (id={client_id}) was not closed. "
            "Call 'await client.close()' or use 'async with' to ensure cleanup.",
            ResourceWarning,
            stacklevel=2,
        )

    # ---------------------------------------------------------------------
    # Factory method: connect()
    # ---------------------------------------------------------------------

    @classmethod
    async def connect(
        cls,
        url: str,
        *,
        transport: str = "streamable-http",
        capabilities: ClientCapabilitiesConfig | None = None,
        client_info: Implementation | None = None,
        timeout: float = 30,
        sse_read_timeout: float = 300,
        headers: dict[str, str] | None = None,
        auth: httpx.Auth | None = None,
        _transport_override: Any = None,
    ) -> MCPClient:
        """Connect to an MCP server and return an initialized client.

        This factory method establishes the connection, performs the MCP
        handshake, and returns a ready-to-use client. Call `close()` when
        done, or use as a context manager.

        Args:
            url: MCP server URL (e.g., "http://localhost:8000/mcp")
            transport: Transport type ("streamable-http" or "lambda-http")
            capabilities: Optional client capability handlers
            client_info: Client implementation metadata
            timeout: Request timeout in seconds
            sse_read_timeout: SSE read timeout in seconds
            headers: Optional HTTP headers
            auth: Optional httpx.Auth handler for authorization. Use
                `dedalus_mcp.dpop.DPoPAuth` for DPoP-bound tokens.
            _transport_override: Internal use only (for testing)

        Returns:
            An initialized MCPClient ready for operations.

        Example:
            client = await MCPClient.connect("http://localhost:8000/mcp")
            tools = await client.list_tools()
            await client.close()
        """
        # For testing: allow injecting a fake session directly
        if _transport_override is not None:
            client = cls.__new__(cls)
            client._read_stream = None  # type: ignore[assignment]
            client._write_stream = None  # type: ignore[assignment]
            client._client_info = client_info
            client._get_session_id = None
            client._exit_stack = None
            client._config = capabilities or ClientCapabilitiesConfig()
            client._supports_roots = client._config.enable_roots or client._config.initial_roots is not None
            client._root_lock = Lock()
            client._roots_version = 0
            client._roots = []
            client._session = _transport_override
            client._closed = False
            client._finalizer = weakref.finalize(client, cls._warn_unclosed, id(client))

            # Initialize the session
            client.initialize_result = await _transport_override.initialize()
            return client

        # Real implementation: use transport helpers
        from mcp.client.streamable_http import MCP_PROTOCOL_VERSION, streamable_http_client
        from mcp.shared._httpx_utils import create_mcp_http_client
        from mcp.types import LATEST_PROTOCOL_VERSION

        from .transports import lambda_http_client

        exit_stack = AsyncExitStack()

        try:
            try:
                # Build httpx client with MCP-appropriate settings
                base_headers: dict[str, str] = {MCP_PROTOCOL_VERSION: LATEST_PROTOCOL_VERSION}
                if headers:
                    base_headers.update(headers)

                http_client = create_mcp_http_client(
                    headers=base_headers,
                    timeout=httpx.Timeout(timeout, read=sse_read_timeout),
                    auth=auth,
                )
                await exit_stack.enter_async_context(http_client)

                transport_lower = transport.lower()
                if transport_lower in {"streamable-http", "streamable_http", "shttp", "http"}:
                    read_stream, write_stream, get_session_id = await exit_stack.enter_async_context(
                        streamable_http_client(url, http_client=http_client)
                    )
                elif transport_lower in {"lambda-http", "lambda_http"}:
                    read_stream, write_stream, get_session_id = await exit_stack.enter_async_context(
                        lambda_http_client(url, http_client=http_client)
                    )
                else:
                    raise ValueError(f"Unsupported transport: {transport}")

                # Create client with exit stack for cleanup
                client = cls(
                    read_stream,
                    write_stream,
                    capabilities=capabilities,
                    client_info=client_info,
                    get_session_id=get_session_id,
                    _exit_stack=exit_stack,
                )

                # Enter the session context
                session = ClientSession(
                    read_stream,
                    write_stream,
                    sampling_callback=client._build_sampling_handler(),
                    elicitation_callback=client._build_elicitation_handler(),
                    list_roots_callback=client._build_roots_handler(),
                    logging_callback=client._build_logging_handler(),
                    client_info=client._client_info,
                )
                client._session = await exit_stack.enter_async_context(session)
                client.initialize_result = await client._session.initialize()

                # Transfer ownership of exit_stack - don't close it here
                exit_stack = None  # type: ignore[assignment]
                return client

            finally:
                # Only close if we didn't transfer ownership
                if exit_stack is not None:
                    await exit_stack.aclose()

        except (httpx.ConnectError, httpx.TimeoutException) as e:
            raise network_error_to_mcp_error(e) from e

        except httpx.HTTPStatusError as e:
            raise http_error_to_mcp_error(e) from e

        except BaseExceptionGroup as e:
            # MCP SDK transport wraps errors in ExceptionGroup from anyio
            http_error = extract_http_error(e)
            if http_error is not None:
                raise http_error_to_mcp_error(http_error) from e

            # Check for network errors in the group
            network_error = extract_network_error(e)
            if network_error is not None:
                raise network_error_to_mcp_error(network_error) from e

            # Not an HTTP or network error - re-raise the group
            raise

        except Exception as e:
            # Handle MCP SDK errors (e.g., McpError for session terminated)
            from mcp.shared.exceptions import McpError

            if isinstance(e, McpError):
                err_msg = str(e).lower()
                if "session" in err_msg and ("terminated" in err_msg or "expired" in err_msg):
                    raise SessionExpiredError(f"Session expired or terminated: {e}") from e
                raise MCPConnectionError(f"MCP error: {e}") from e

            # Check for network errors that might not be caught above
            if isinstance(e.__cause__, (httpx.ConnectError, httpx.TimeoutException)):
                raise network_error_to_mcp_error(e.__cause__) from e
            raise

    # ---------------------------------------------------------------------
    # Cleanup: close()
    # ---------------------------------------------------------------------

    async def close(self) -> None:
        """Close the client and release all resources.

        This method is idempotent - calling it multiple times is safe.
        After calling close(), the client cannot be used for operations.
        """
        if self._closed:
            return

        self._closed = True
        self._finalizer.detach()  # Don't warn since we're closing properly

        if self._exit_stack is not None:
            await self._exit_stack.aclose()
            self._exit_stack = None

        self._session = None
        self.initialize_result = None

    # ---------------------------------------------------------------------
    # Async context manager
    # ---------------------------------------------------------------------

    async def __aenter__(self) -> MCPClient:
        if self._closed:
            raise RuntimeError("Cannot use closed MCPClient as context manager")

        # If we already have a session (from connect()), just return self
        if self._session is not None:
            return self

        # Legacy path: initialize from streams
        session = ClientSession(
            self._read_stream,
            self._write_stream,
            sampling_callback=self._build_sampling_handler(),
            elicitation_callback=self._build_elicitation_handler(),
            list_roots_callback=self._build_roots_handler(),
            logging_callback=self._build_logging_handler(),
            client_info=self._client_info,
        )

        exit_stack = AsyncExitStack()
        try:
            self._session = await exit_stack.enter_async_context(session)
            self.initialize_result = await self._session.initialize()
        except Exception:
            await exit_stack.aclose()
            raise
        else:
            self._exit_stack = exit_stack
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> bool | None:
        await self.close()
        return None

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------

    @property
    def session(self) -> ClientSession:
        if self._closed:
            raise RuntimeError("Client is closed")
        if self._session is None:
            raise RuntimeError("Client session not started; use 'async with' or connect() first.")
        return self._session

    @property
    def session_id(self) -> str | None:
        """Return the Mcp-Session-Id assigned by the server.

        Returns None if no session ID was assigned or before initialization.

        See more: https://modelcontextprotocol.io/specification/2025-06-18/basic/transports#session-management
        """
        if self._get_session_id is None:
            return None
        return self._get_session_id()

    @property
    def supports_roots(self) -> bool:
        """Whether the client advertises the roots capability."""
        return self._supports_roots

    async def ping(self) -> EmptyResult:
        """Send ping to verify liveness.

        See: https://modelcontextprotocol.io/specification/2024-11-05/basic/utilities/ping
        """
        return await self.send_request(ClientRequest(PingRequest()), EmptyResult)

    async def send_request(
        self,
        request: ClientRequest,
        result_type: type[T_RequestResult],
        *,
        progress_callback: Callable[[float, float | None, str | None], Awaitable[None] | None] | None = None,
    ) -> T_RequestResult:
        """Forward a request to the server and await the result."""
        return await self.session.send_request(request, result_type, progress_callback=progress_callback)

    async def cancel_request(self, request_id: RequestId, *, reason: str | None = None) -> None:
        """Emit notifications/cancelled.

        See: https://modelcontextprotocol.io/specification/2024-11-05/basic/utilities/cancellation
        """
        params = CancelledNotificationParams(requestId=request_id, reason=reason)
        notification = ClientNotification(CancelledNotification(params=params))
        await self.session.send_notification(notification)

    async def update_roots(self, roots: Iterable[Root | dict[str, Any]], *, notify: bool = True) -> None:
        """Replace the advertised roots and optionally send roots/list_changed.

        See: https://modelcontextprotocol.io/specification/2024-11-05/client/roots

        """
        if not self._supports_roots:
            raise RuntimeError("Roots capability is not enabled for this client")

        normalized = [self._normalize_root(root) for root in roots]
        async with self._root_lock:
            self._roots_version += 1
            self._roots = normalized

        if notify and self._session is not None:
            await self._session.send_roots_list_changed()

    async def list_roots(self) -> list[Root]:
        """Return the current set of roots advertised to servers."""
        async with self._root_lock:
            return [root.model_copy(deep=True) for root in self._roots]

    def roots_version(self) -> int:
        return self._roots_version

    # ------------------------------------------------------------------
    # Convenience methods for common operations
    # ------------------------------------------------------------------

    async def list_tools(self) -> ListToolsResult:
        """List all tools available on the server.

        See: https://modelcontextprotocol.io/specification/2024-11-05/server/tools
        """
        return await self.session.list_tools()

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> CallToolResult:
        """Call a tool on the server.

        See: https://modelcontextprotocol.io/specification/2024-11-05/server/tools
        """
        return await self.session.call_tool(name, arguments)

    async def list_resources(self) -> ListResourcesResult:
        """List all resources available on the server.

        See: https://modelcontextprotocol.io/specification/2024-11-05/server/resources
        """
        return await self.session.list_resources()

    async def read_resource(self, uri: str) -> ReadResourceResult:
        """Read a resource from the server.

        See: https://modelcontextprotocol.io/specification/2024-11-05/server/resources
        """
        return await self.session.read_resource(uri)

    async def list_prompts(self) -> ListPromptsResult:
        """List all prompts available on the server.

        See: https://modelcontextprotocol.io/specification/2024-11-05/server/prompts
        """
        return await self.session.list_prompts()

    async def get_prompt(self, name: str, arguments: dict[str, Any] | None = None) -> GetPromptResult:
        """Get a prompt from the server.

        See: https://modelcontextprotocol.io/specification/2024-11-05/server/prompts
        """
        return await self.session.get_prompt(name, arguments)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_sampling_handler(self) -> Callable[[Any, CreateMessageRequestParams], Awaitable[Any]] | None:
        handler = self._config.sampling
        if handler is None:
            return None

        async def wrapper(context: Any, params: CreateMessageRequestParams) -> Any:
            return await maybe_await_with_args(handler, context, params)

        return wrapper

    def _build_elicitation_handler(self) -> Callable[[Any, ElicitRequestParams], Awaitable[Any]] | None:
        handler = self._config.elicitation
        if handler is None:
            return None

        async def wrapper(context: Any, params: ElicitRequestParams) -> Any:
            return await maybe_await_with_args(handler, context, params)

        return wrapper

    def _build_logging_handler(self) -> Callable[[LoggingMessageNotificationParams], Awaitable[None]] | None:
        handler = self._config.logging
        if handler is None:
            return None

        async def wrapper(params: LoggingMessageNotificationParams) -> None:
            await maybe_await_with_args(handler, params)

        return wrapper

    def _build_roots_handler(self) -> Callable[[Any], Awaitable[ClientResult]] | None:
        if not self._supports_roots:
            return None

        async def list_roots_handler(_: Any) -> ListRootsResult:
            async with self._root_lock:
                roots_snapshot = [root.model_copy(deep=True) for root in self._roots]
            return ListRootsResult(roots=roots_snapshot)

        return list_roots_handler

    @staticmethod
    def _normalize_root(value: Root | dict[str, Any]) -> Root:
        if isinstance(value, Root):
            return value
        return Root.model_validate(value)


__all__ = ["MCPClient", "ClientCapabilitiesConfig"]
