# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Lightweight client-side diagnostics for MCP request lifecycles."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import time
from typing import Any

from ..types.messages import ClientRequest


@dataclass(frozen=True, slots=True)
class ClientRequestRecord:
    """Privacy-safe metadata for a completed client request."""

    sequence: int
    method: str
    result_type: str
    session_id: str | None
    started_at_ns: int
    duration_ms: float
    ok: bool
    error_type: str | None = None
    error_message: str | None = None


class ClientRequestHistory:
    """Bounded request history for debugging MCP client sessions.

    The history intentionally stores only operational metadata. It does not
    retain request parameters, tool arguments, resource URIs, or result payloads.
    """

    def __init__(self, *, max_records: int = 128) -> None:
        if max_records <= 0:
            msg = "max_records must be greater than 0"
            raise ValueError(msg)

        self._records: deque[ClientRequestRecord] = deque(maxlen=max_records)
        self._next_sequence = 1

    def snapshot(self) -> tuple[ClientRequestRecord, ...]:
        """Return records in oldest-to-newest order."""
        return tuple(self._records)

    def clear(self) -> None:
        """Drop all retained request records."""
        self._records.clear()

    def record_success(
        self,
        *,
        request: ClientRequest,
        result_type: type[Any],
        session_id: str | None,
        started_at_ns: int,
        duration_ms: float,
    ) -> None:
        self._append(
            method=request_method(request),
            result_type=result_type,
            session_id=session_id,
            started_at_ns=started_at_ns,
            duration_ms=duration_ms,
            ok=True,
        )

    def record_method_success(
        self, *, method: str, result_type: type[Any], session_id: str | None, started_at_ns: int, duration_ms: float
    ) -> None:
        self._append(
            method=method,
            result_type=result_type,
            session_id=session_id,
            started_at_ns=started_at_ns,
            duration_ms=duration_ms,
            ok=True,
        )

    def record_error(
        self,
        *,
        request: ClientRequest,
        result_type: type[Any],
        session_id: str | None,
        started_at_ns: int,
        duration_ms: float,
        error: BaseException,
    ) -> None:
        self._append(
            method=request_method(request),
            result_type=result_type,
            session_id=session_id,
            started_at_ns=started_at_ns,
            duration_ms=duration_ms,
            ok=False,
            error_type=type(error).__name__,
            error_message=str(error)[:500],
        )

    def record_method_error(
        self,
        *,
        method: str,
        result_type: type[Any],
        session_id: str | None,
        started_at_ns: int,
        duration_ms: float,
        error: BaseException,
    ) -> None:
        self._append(
            method=method,
            result_type=result_type,
            session_id=session_id,
            started_at_ns=started_at_ns,
            duration_ms=duration_ms,
            ok=False,
            error_type=type(error).__name__,
            error_message=str(error)[:500],
        )

    def _append(
        self,
        *,
        method: str,
        result_type: type[Any],
        session_id: str | None,
        started_at_ns: int,
        duration_ms: float,
        ok: bool,
        error_type: str | None = None,
        error_message: str | None = None,
    ) -> None:
        self._records.append(
            ClientRequestRecord(
                sequence=self._next_sequence,
                method=method,
                result_type=result_type.__name__,
                session_id=session_id,
                started_at_ns=started_at_ns,
                duration_ms=round(duration_ms, 3),
                ok=ok,
                error_type=error_type,
                error_message=error_message,
            )
        )
        self._next_sequence += 1


def request_method(request: ClientRequest) -> str:
    """Return the JSON-RPC method name for a typed client request."""
    root = getattr(request, "root", None)
    method = getattr(root, "method", None)
    if isinstance(method, str) and method:
        return method
    return type(root).__name__ if root is not None else type(request).__name__


def elapsed_ms_since(started_at_ns: int) -> float:
    """Return elapsed monotonic time in milliseconds."""
    return (time.perf_counter_ns() - started_at_ns) / 1_000_000


__all__ = ["ClientRequestHistory", "ClientRequestRecord", "elapsed_ms_since", "request_method"]
