# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Request context helpers for Dedalus MCP handlers.

The utilities in this module provide a stable surface over the reference
SDK's ``request_ctx`` primitive so application code can access
capabilities such as logging and progress without importing SDK internals.

Implements context integration for MCP capabilities:

- https://modelcontextprotocol.io/specification/2025-06-18/server/utilities/logging
  (server-to-client logging notifications)
- https://modelcontextprotocol.io/specification/2025-06-18/basic/utilities/progress
  (progress notifications during long-running operations)
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from mcp.server.lowlevel.server import request_ctx
from mcp.shared.context import RequestContext
from mcp.types import LoggingLevel, ProgressToken

from .progress import ProgressConfig, ProgressTelemetry, ProgressTracker
from .progress import progress as progress_manager


if TYPE_CHECKING:
    from mcp.server.session import ServerSession
    from .dispatch import DispatchResponse
    from .server.connectors import Connection
    from .server.core import MCPServer
    from .server.dependencies.models import DependencyCall, ResolvedDependency
    from .server.resolver import ConnectionResolver


_CURRENT_CONTEXT: ContextVar[Context | None] = ContextVar("dedalus_mcp_current_context", default=None)
RUNTIME_CONTEXT_KEY = "dedalus_mcp.runtime"


def get_context() -> Context:
    """Return the active :class:`Context`.

    Raises:
        LookupError: If called outside of an MCP request handler.

    Example::

        from dedalus_mcp import get_context, tool


        @tool(description="Reports its own request id")
        async def whoami() -> str:
            ctx = get_context()
            await ctx.info("Handling whoami request")
            return ctx.request_id
    """
    ctx = _CURRENT_CONTEXT.get()
    if ctx is None:
        raise LookupError("No active context; use get_context() from within a request handler")
    return ctx


@dataclass(slots=True)
class Context:
    """Lightweight façade over the SDK request context.

    This wrapper keeps Dedalus MCP applications within the framework surface
    while still enabling access to logging and progress utilities mandated
    by the MCP specification.
    """

    _request_context: RequestContext
    dependency_cache: dict["DependencyCall", "ResolvedDependency"] | None = None
    runtime: Mapping[str, Any] | None = None

    # ------------------------------------------------------------------
    # Introspection helpers
    # ------------------------------------------------------------------

    @property
    def request_id(self) -> str:
        """Return the request identifier assigned by the SDK."""
        return str(self._request_context.request_id)

    @property
    def session(self) -> ServerSession:
        """Expose the underlying session for advanced scenarios."""
        return self._request_context.session

    @property
    def server(self) -> "MCPServer" | None:
        """Return the MCP server associated with this request, if any."""

        runtime = self.runtime
        if not isinstance(runtime, Mapping):
            return None
        return cast("MCPServer | None", runtime.get("server"))

    @property
    def session_id(self) -> str | None:
        """Return the Mcp-Session-Id from the request headers.

        Per the MCP specification, servers MAY assign a session ID during
        initialization via the Mcp-Session-Id header. This property extracts
        that session ID from subsequent requests.

        Returns None for transports without session IDs (e.g., STDIO).

        See more: https://modelcontextprotocol.io/specification/2025-06-18/basic/transports#session-management
        """
        request = getattr(self._request_context, "request", None)
        if request is None:
            return None
        headers = getattr(request, "headers", None)
        if headers is None:
            return None
        return headers.get("mcp-session-id")

    @property
    def progress_token(self) -> ProgressToken | None:
        """Return the progress token supplied by the client, if any."""
        meta = self._request_context.meta
        return None if meta is None else getattr(meta, "progressToken", None)

    @property
    def auth_context(self) -> Any | None:
        """Return the authorization context populated by transports, if present."""
        scope = self._request_scope()
        if isinstance(scope, Mapping):
            return scope.get("dedalus_mcp.auth")
        return None

    @property
    def resolver(self) -> "ConnectionResolver" | None:
        """Return the configured connection resolver for this server, if any."""
        runtime = self.runtime
        if not isinstance(runtime, Mapping):
            return None
        resolver = runtime.get("resolver")
        if resolver is None:
            return None
        return cast("ConnectionResolver", resolver)

    # ------------------------------------------------------------------
    # Logging conveniences
    # See: https://modelcontextprotocol.io/specification/2025-06-18/server/utilities/logging
    # ------------------------------------------------------------------

    async def log(
        self,
        level: LoggingLevel | str,
        message: str,
        *,
        logger: str | None = None,
        data: Mapping[str, Any] | None = None,
    ) -> None:
        """Send a log message to the client.

        Args:
            level: Severity level defined by the MCP logging capability.
            message: Human-readable message describing the event.
            logger: Optional logger name for client-side routing.
            data: Optional structured payload merged into the log body.
        """
        payload: dict[str, Any] = {"msg": message}
        if data:
            payload.update(dict(data))

        await self._request_context.session.send_log_message(level=level, data=payload, logger=logger)

    async def debug(self, message: str, *, logger: str | None = None, data: Mapping[str, Any] | None = None) -> None:
        await self.log("debug", message, logger=logger, data=data)

    async def info(self, message: str, *, logger: str | None = None, data: Mapping[str, Any] | None = None) -> None:
        await self.log("info", message, logger=logger, data=data)

    async def warning(self, message: str, *, logger: str | None = None, data: Mapping[str, Any] | None = None) -> None:
        await self.log("warning", message, logger=logger, data=data)

    async def error(self, message: str, *, logger: str | None = None, data: Mapping[str, Any] | None = None) -> None:
        await self.log("error", message, logger=logger, data=data)

    # ------------------------------------------------------------------
    # Progress helpers
    # See: https://modelcontextprotocol.io/specification/2025-06-18/basic/utilities/progress
    # ------------------------------------------------------------------

    async def report_progress(self, progress: float, *, total: float | None = None, message: str | None = None) -> None:
        """Emit a single progress notification if the client requested one."""
        token = self.progress_token
        if token is None:
            return

        await self._request_context.session.send_progress_notification(
            progress_token=token, progress=progress, total=total, message=message
        )

    def progress(
        self,
        total: float | None = None,
        *,
        config: ProgressConfig | None = None,
        telemetry: ProgressTelemetry | None = None,
    ) -> AsyncIterator[ProgressTracker]:
        """Return the coalescing progress context manager for this request."""
        return progress_manager(total=total, config=config, telemetry=telemetry)

    async def resolve_client(self, handle: str, *, operation: Mapping[str, Any] | None = None) -> Any:
        """Resolve a connection handle into a driver client via the configured resolver."""

        if not isinstance(handle, str):
            raise TypeError("Connection handle must be a string identifier")

        resolver = self.resolver
        if resolver is None:
            raise RuntimeError("Connection resolver is not configured for this server")

        request_payload = self._build_resolver_context(operation)
        return await resolver.resolve_client(handle, request_payload)

    async def dispatch(
        self,
        target: "Connection | str | None" = None,
        request: Any = None,
        /,
    ) -> "DispatchResponse":
        """Execute authenticated HTTP request through dispatch backend.

        Single-connection server (target omitted):
            ctx.dispatch(HttpRequest(method=HttpMethod.GET, path="/user"))

        Multi-connection server (target required):
            ctx.dispatch(github, HttpRequest(method=HttpMethod.GET, path="/user"))
            ctx.dispatch("github", HttpRequest(...))

        Args:
            target: Connection to use. Required for multi-connection servers.
                    Can be Connection object or string name.
                    Omit for single-connection servers.
            request: HttpRequest to execute.

        Returns:
            DispatchResponse with HTTP response or error

        Raises:
            RuntimeError: If dispatch backend or connections not configured
            ValueError: If target required but not provided
            InvalidConnectionHandleError: If handle format is invalid

        Example:
            >>> response = await ctx.dispatch(HttpRequest(
            ...     method=HttpMethod.POST,
            ...     path="/repos/owner/repo/issues",
            ...     body={"title": "Bug", "body": "Description"},
            ... ))
            >>> if response.success:
            ...     print(response.response.body)
        """
        from .dispatch import (
            DispatchBackend,
            DispatchResponse,
            DispatchWireRequest,
            HttpRequest,
        )
        from .server.connectors import Connection
        from .server.services.connection_gate import validate_handle_format

        # Handle overloaded signature: dispatch(HttpRequest) or dispatch(target, HttpRequest)
        if request is None:
            # Single arg: target is actually the request
            if target is None:
                raise ValueError("request is required")
            if not isinstance(target, HttpRequest):
                raise TypeError(f"expected HttpRequest, got {type(target).__name__}")
            http_request = target
            connection_target = None
        else:
            if not isinstance(request, HttpRequest):
                raise TypeError(f"expected HttpRequest, got {type(request).__name__}")
            http_request = request
            connection_target = target

        # Get runtime config
        runtime = self.runtime
        if not isinstance(runtime, Mapping):
            raise RuntimeError("Dispatch backend not configured")

        backend = runtime.get("dispatch_backend")
        if backend is None or not isinstance(backend, DispatchBackend):
            raise RuntimeError("Dispatch backend not configured")

        # Resolve connection target to handle
        connections = self._get_connections(runtime)

        if connection_target is None:
            # Single-connection server: use the only connection
            if len(connections) == 0:
                raise RuntimeError("No connections configured")
            if len(connections) > 1:
                raise ValueError("Multiple connections configured; target is required")
            connection_handle = next(iter(connections.values()))
        elif isinstance(connection_target, str):
            # String name lookup
            if connection_target not in connections:
                available = list(connections.keys())
                raise ValueError(f"Connection '{connection_target}' not found. Available: {available}")
            connection_handle = connections[connection_target]
        elif isinstance(connection_target, Connection):
            # Connection object lookup
            if connection_target.name not in connections:
                available = list(connections.keys())
                raise ValueError(f"Connection '{connection_target.name}' not found. Available: {available}")
            connection_handle = connections[connection_target.name]
        else:
            raise TypeError(f"target must be Connection, str, or None; got {type(connection_target).__name__}")

        # Validate handle format (authorization is done by gateway at runtime)
        validate_handle_format(connection_handle)

        # Extract JWT from ASGI headers
        from .server.authorization import parse_authorization_token
        from .utils import get_logger

        _ctx_logger = get_logger("dedalus_mcp.context")
        authorization_token = None
        scope = self._request_scope()

        if isinstance(scope, Mapping):
            headers = scope.get("headers", [])

            for name, value in headers:
                if name == b"authorization":
                    raw_value = value.decode("latin1")
                    _ctx_logger.debug(f"Extracting auth from ASGI scope: {raw_value[:40]}...")
                    authorization_token = parse_authorization_token(raw_value)
                    if authorization_token:
                        _ctx_logger.debug("Successfully parsed authorization token for dispatch")
                    else:
                        _ctx_logger.warning(f"Failed to parse Authorization header format: {raw_value[:60]}")
                    break

            if not authorization_token:
                # Log all header names for debugging missing auth
                header_names = [n.decode() if isinstance(n, bytes) else str(n) for n, _ in headers[:10]]
                _ctx_logger.warning(f"No Authorization header in ASGI scope. Available headers: {', '.join(header_names)}")

        # Dedalus-hosted MCP servers require Authorization tokens
        if os.getenv("DEDALUS_DISPATCH_URL") and not authorization_token:
            dispatch_url = os.getenv("DEDALUS_DISPATCH_URL")
            msg = f"""DEDALUS_DISPATCH_URL is set ({dispatch_url}), which requires JWT authorization from the client.
        Either:
        1) Unset DEDALUS_DISPATCH_URL to use OSS mode (direct API calls with local credentials)
        2) Use the Dedalus SDK client that sends the proper Authorization headers
        """
            raise RuntimeError(msg)

        # Build and execute wire request
        wire_request = DispatchWireRequest(
            connection_handle=connection_handle,
            request=http_request,
            authorization=authorization_token,
        )

        return await backend.dispatch(wire_request)

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    @classmethod
    def from_request_context(cls, request_context: RequestContext) -> Context:
        """Build a :class:`Context` from the SDK request context."""
        runtime_payload: Mapping[str, Any] | None = None
        lifespan_context = request_context.lifespan_context
        if isinstance(lifespan_context, Mapping):
            candidate = lifespan_context.get(RUNTIME_CONTEXT_KEY)
            if candidate is not None and isinstance(candidate, Mapping):
                runtime_payload = cast(Mapping[str, Any], candidate)
        return cls(_request_context=request_context, runtime=runtime_payload)

    def _request_scope(self) -> Mapping[str, Any] | None:
        request = getattr(self._request_context, "request", None)
        if request is None:
            return None
        return getattr(request, "scope", None)

    def _build_resolver_context(self, operation: Mapping[str, Any] | None) -> dict[str, Any]:
        auth_context = self.auth_context
        if auth_context is None:
            raise RuntimeError("Authorization context missing; cannot resolve connection handle")
        payload: dict[str, Any] = {"dedalus_mcp.auth": auth_context}
        if operation is not None:
            payload["operation"] = dict(operation)
        return payload

    def _get_connections(self, runtime: Mapping[str, Any]) -> dict[str, str]:
        """Get connection mapping from JWT claims (ddls:connections)."""
        auth_context = self.auth_context
        if auth_context is None:
            msg = (
                "Authorization context is None. "
                "Ensure MCPServer has authorization=AuthorizationConfig() configured "
                "and the client sends a valid JWT in the Authorization header."
            )
            raise RuntimeError(msg)

        claims = getattr(auth_context, "claims", None)
        if not isinstance(claims, dict):
            raise RuntimeError("Invalid authorization claims")

        connections = claims.get("ddls:connections")
        if not isinstance(connections, dict):
            raise RuntimeError("Missing required JWT claims for connection resolution")

        return dict(connections)


def _activate_request_context() -> Token[Context | None]:
    """Populate the ambient context var from the SDK request context."""
    request_context = request_ctx.get()
    context = Context.from_request_context(request_context)
    return _CURRENT_CONTEXT.set(context)


def _reset_context(token: Token[Context | None]) -> None:
    """Restore the previous context after a handler completes."""
    _CURRENT_CONTEXT.reset(token)


@contextmanager
def context_scope() -> Iterator[Context | None]:
    """Context manager that activates the current request context.

    Yields None if no request context is available (e.g., during testing).
    """
    try:
        token = _activate_request_context()
    except LookupError:
        # No request context available (e.g., direct service method calls in tests)
        yield None
        return

    try:
        yield get_context()
    finally:
        _reset_context(token)


__all__ = ["Context", "RUNTIME_CONTEXT_KEY", "get_context", "context_scope"]
