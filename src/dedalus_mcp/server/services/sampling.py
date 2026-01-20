# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Sampling capability service for LLM interaction requests."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING
import weakref

import anyio
from mcp.server.lowlevel.server import request_ctx
from mcp.shared.exceptions import McpError

from ... import types
from ...utils import get_logger


if TYPE_CHECKING:
    from mcp.server.session import ServerSession


@dataclass
class _SessionState:
    semaphore: asyncio.Semaphore
    consecutive_failures: int = 0
    cooldown_until: float = 0.0
    request_counter: int = 0


class SamplingService:
    """Proxy for ``sampling/createMessage`` requests.

    See: https://modelcontextprotocol.io/specification/2025-06-18/client/sampling

    Args:
        timeout: Request timeout in seconds.
        max_concurrent: Max concurrent sampling requests per session.
        failure_threshold: Consecutive failures before cooldown.
        cooldown_seconds: Cooldown duration after hitting failure threshold.
    """

    def __init__(
        self,
        *,
        timeout: float = 60.0,
        max_concurrent: int = 4,
        failure_threshold: int = 3,
        cooldown_seconds: float = 30.0,
    ) -> None:
        self._timeout = timeout
        self._max_concurrent = max(1, max_concurrent)
        self._failure_threshold = failure_threshold
        self._cooldown_seconds = cooldown_seconds
        # Sessions are kept alive by the SDK; WeakKeyDictionary auto-cleans when sessions are garbage collected
        self._states: weakref.WeakKeyDictionary[ServerSession, _SessionState] = weakref.WeakKeyDictionary()
        self._logger = get_logger("dedalus_mcp.sampling")

    async def create_message(self, params: types.CreateMessageRequestParams) -> types.CreateMessageResult:
        session = self._current_session()

        if not session.check_client_capability(types.ClientCapabilities(sampling=types.SamplingCapability())):
            raise McpError(
                types.ErrorData(
                    code=types.METHOD_NOT_FOUND, message="Client does not advertise the sampling capability"
                )
            )

        state = self._states.setdefault(session, _SessionState(asyncio.Semaphore(self._max_concurrent)))
        async with state.semaphore:
            await self._enforce_cooldown(state)
            state.request_counter += 1
            metadata = (params.metadata or {}).copy()  # type: ignore[attr-defined]
            if "requestId" not in metadata:
                metadata["requestId"] = f"sampling-{id(self)}-{state.request_counter}"
            params.metadata = metadata  # type: ignore[attr-defined]

            try:
                with anyio.fail_after(self._timeout):
                    request = types.ServerRequest(types.CreateMessageRequest(params=params))
                    result = await session.send_request(request, types.CreateMessageResult)
            except TimeoutError:
                state.consecutive_failures += 1
                state.cooldown_until = anyio.current_time() + self._cooldown_seconds
                raise McpError(
                    types.ErrorData(code=types.INTERNAL_ERROR, message="sampling request timed out")
                ) from None
            except McpError as exc:
                state.consecutive_failures += 1
                raise exc
            else:
                state.consecutive_failures = 0
                return result

    async def _enforce_cooldown(self, state: _SessionState) -> None:
        if state.consecutive_failures < self._failure_threshold:
            return
        remaining = state.cooldown_until - anyio.current_time()
        if remaining > 0:
            raise McpError(
                types.ErrorData(
                    code=types.SERVICE_UNAVAILABLE, message="sampling temporarily unavailable; please retry later"
                )
            )
        state.consecutive_failures = 0

    def _current_session(self):
        try:
            ctx = request_ctx.get()
        except LookupError as exc:
            raise RuntimeError("Sampling requests require an active MCP session") from exc
        return ctx.session


__all__ = ["SamplingService"]
