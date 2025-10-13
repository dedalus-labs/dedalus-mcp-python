"""High-level client/session helpers built on top of the reference SDK.

The handshake follows the steps mandated by ``docs/mcp/core/lifecycle/lifecycle-phases.md``
— issuing ``initialize`` immediately and acknowledging with
``notifications/initialized`` once the server responds.
"""

from __future__ import annotations

from typing import Any

from .._sdk_loader import ensure_sdk_importable

ensure_sdk_importable()

from typing import TYPE_CHECKING
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
from mcp.client.session import (
    ClientSession,
    ElicitationFnT,
    ListRootsFnT,
    LoggingFnT,
    SamplingFnT,
)

if TYPE_CHECKING:
    from mcp import types

class MCPClient:
    """Lifecycle-aware wrapper around :class:`mcp.client.session.ClientSession`.

    On entry the client performs the initialization exchange described in the
    specification, verifying the negotiated protocol version and emitting the
    ``notifications/initialized`` marker (see
    ``docs/mcp/core/lifecycle/lifecycle-phases.md``).
    """

    def __init__(
        self,
        read_stream: MemoryObjectReceiveStream[Any],
        write_stream: MemoryObjectSendStream[Any],
        *,
        sampling_callback: SamplingFnT | None = None,
        elicitation_callback: ElicitationFnT | None = None,
        list_roots_callback: ListRootsFnT | None = None,
        logging_callback: LoggingFnT | None = None,
        client_info: types.Implementation | None = None,
    ) -> None:
        self._read_stream = read_stream
        self._write_stream = write_stream
        self._sampling_callback = sampling_callback
        self._elicitation_callback = elicitation_callback
        self._list_roots_callback = list_roots_callback
        self._logging_callback = logging_callback
        self._client_info = client_info
        self._session: ClientSession | None = None
        self.initialize_result: types.InitializeResult | None = None

    async def __aenter__(self) -> "MCPClient":
        self._session = await ClientSession(
            self._read_stream,
            self._write_stream,
            sampling_callback=self._sampling_callback,
            elicitation_callback=self._elicitation_callback,
            list_roots_callback=self._list_roots_callback,
            logging_callback=self._logging_callback,
            client_info=self._client_info,
        ).__aenter__()
        self.initialize_result = await self._session.initialize()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool | None:
        if self._session is None:
            return None
        return await self._session.__aexit__(exc_type, exc, tb)

    @property
    def session(self) -> ClientSession:
        if self._session is None:
            raise RuntimeError("Client session not started; use 'async with' before accessing it.")
        return self._session

    async def ping(self) -> types.EmptyResult:
        """Send ``ping`` to verify liveness (``docs/mcp/spec/schema-reference/ping.md``)."""
        return await self.session.send_ping()

    async def notify_progress(
        self,
        token: types.ProgressToken,
        *,
        progress: float,
        total: float | None = None,
        message: str | None = None,
    ) -> None:
        """Emit ``notifications/progress`` (``docs/mcp/spec/schema-reference/notifications-progress.md``)."""
        await self.session.send_progress_notification(
            progress_token=token,
            progress=progress,
            total=total,
            message=message,
        )

    async def send_request(
        self,
        request: types.ClientRequest,
        result_type: type[Any],
        *,
        progress_callback: Any | None = None,
    ) -> Any:
        """Forward a request to the server and await the result.

        The helper preserves the semantics described in
        ``docs/mcp/spec/overview/messages.md`` by funnelling the call through the
        managed :class:`ClientSession`.
        """
        return await self.session.send_request(
            request,
            result_type,
            progress_callback=progress_callback,
        )


__all__ = ["MCPClient"]
