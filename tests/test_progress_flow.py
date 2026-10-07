# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import anyio
from mcp import types
from mcp.server.lowlevel.server import request_ctx
from mcp.shared.context import RequestContext
import pytest

from dedalus_mcp.progress import (
    ProgressCloseEvent,
    ProgressConfig,
    ProgressEmitEvent,
    ProgressLifecycleEvent,
    ProgressTelemetry,
    progress,
)


@dataclass
class RecordedNotification:
    token: types.ProgressToken
    progress: float
    total: float | None
    message: str | None


class FakeSession:
    def __init__(self) -> None:
        self.notifications: list[RecordedNotification] = []

    async def send_progress_notification(
        self,
        progress_token: str | int,
        progress_value: float,
        *,
        total: float | None = None,
        message: str | None = None,
    ) -> None:
        self.notifications.append(RecordedNotification(progress_token, progress_value, total, message))


@asynccontextmanager
async def with_request_context(*, token: types.ProgressToken | None, session: FakeSession) -> AsyncIterator[None]:
    meta = types.RequestParams.Meta(progressToken=token) if token is not None else None
    ctx = RequestContext(request_id=1, meta=meta, session=session, lifespan_context=None)
    token_ctx = request_ctx.set(ctx)
    try:
        yield
    finally:
        request_ctx.reset(token_ctx)


@pytest.mark.anyio
async def test_progress_notifications_roundtrip() -> None:
    session = FakeSession()

    async with with_request_context(token="tok", session=session), progress(total=3) as tracker:
        await tracker.advance(1, "step1")
        await tracker.advance(2, "step3")

    assert session.notifications, "expected at least one notification"
    assert session.notifications[-1] == RecordedNotification("tok", 3, 3, "step3")
    values = [note.progress for note in session.notifications]
    assert values == sorted(values), "progress values must be monotonic"


@pytest.mark.anyio
async def test_progress_without_token_raises() -> None:
    session = FakeSession()

    async with with_request_context(token=None, session=session):
        with pytest.raises(ValueError):
            async with progress(total=1):
                await anyio.sleep(0)


@pytest.mark.anyio
async def test_progress_monotonicity_violation() -> None:
    session = FakeSession()

    async with with_request_context(token="tok", session=session), progress(total=5) as tracker:
        await tracker.set(2)
        with pytest.raises(ValueError):
            await tracker.set(1)


@pytest.mark.anyio
async def test_progress_telemetry_hooks_capture_events() -> None:
    session = FakeSession()
    starts: list[ProgressLifecycleEvent] = []
    emits: list[ProgressEmitEvent] = []
    closes: list[ProgressCloseEvent] = []

    telemetry = ProgressTelemetry(
        on_start=lambda evt: starts.append(evt),
        on_emit=lambda evt: emits.append(evt),
        on_close=lambda evt: closes.append(evt),
    )

    async with with_request_context(token="tok", session=session):
        async with progress(total=4, telemetry=telemetry, config=ProgressConfig(emit_hz=50)) as tracker:
            await tracker.advance(1, "one")
            await anyio.sleep(0.01)
            await tracker.advance(1, "two")
            await tracker.set(4, message="done")
            await anyio.sleep(0.01)

    assert len(starts) == 1 and starts[0].token == "tok"
    assert emits and any(evt.progress == 4 for evt in emits)
    assert closes and closes[-1].final_progress == 4


@pytest.mark.anyio
async def test_progress_throttle_event_emitted() -> None:
    session = FakeSession()
    throttled: list[int] = []

    telemetry = ProgressTelemetry(on_throttle=lambda evt: throttled.append(evt.pending_updates))

    async with with_request_context(token="tok", session=session):
        async with progress(total=2, telemetry=telemetry, config=ProgressConfig(emit_hz=1)) as tracker:
            await tracker.advance(1)
            await anyio.sleep(0.05)
            await tracker.advance(1)

    assert throttled, "expected throttle telemetry when emit_hz is low"
    assert session.notifications[-1].progress == 2


def _assert_monotonic(notifications: list[RecordedNotification]) -> None:
    values = [n.progress for n in notifications]
    assert values == sorted(values), f"progress went backwards: {values}"


@pytest.mark.anyio
async def test_close_during_throttled_send_does_not_regress() -> None:
    """Closing while a throttled update is in flight must not re-send an older value."""
    session = FakeSession()
    closes: list[ProgressCloseEvent] = []
    telemetry = ProgressTelemetry(on_close=lambda evt: closes.append(evt))

    async with with_request_context(token="tok", session=session):
        async with progress(total=4, telemetry=telemetry, config=ProgressConfig(emit_hz=20)) as tracker:
            await tracker.advance(1, "one")
            await anyio.sleep(0.005)  # first update delivered immediately
            await tracker.set(4, message="done")  # throttled
            await anyio.sleep(0.001)  # emitter picks it up; still in flight at close

    _assert_monotonic(session.notifications)
    assert session.notifications[-1].progress == 4
    assert closes
    assert closes[-1].final_progress == 4
    assert closes[-1].final_message == "done"


@pytest.mark.anyio
async def test_advance_uses_in_flight_state_as_base() -> None:
    """``advance`` must build on an update that is in flight, not the last delivered one."""
    session = FakeSession()

    async with with_request_context(token="tok", session=session):
        async with progress(total=10, config=ProgressConfig(emit_hz=20)) as tracker:
            await tracker.advance(1)
            await anyio.sleep(0.005)  # first update delivered immediately
            await tracker.set(3)  # throttled
            await anyio.sleep(0.001)  # emitter picks it up and waits out the throttle
            assert await tracker.advance(1) == 4

    _assert_monotonic(session.notifications)
    assert session.notifications[-1].progress == 4


class HeldSession(FakeSession):
    """FakeSession that holds each send until the test releases it.

    While a send is held, the emitter keeps that state in flight, so tests can act
    inside the race window without relying on sleeps. ``fail_attempts`` lists send
    attempts (1-based, across all sends) that raise after being released.
    """

    def __init__(self, *, fail_attempts: tuple[int, ...] = ()) -> None:
        super().__init__()
        self.attempts = 0
        self._fail_attempts = fail_attempts
        self._holding = True
        self._started = anyio.Event()
        self._gate = anyio.Event()

    async def send_progress_notification(
        self,
        progress_token: str | int,
        progress_value: float,
        *,
        total: float | None = None,
        message: str | None = None,
    ) -> None:
        self.attempts += 1
        attempt = self.attempts
        if self._holding:
            gate = self._gate
            self._started.set()
            await gate.wait()
        if attempt in self._fail_attempts:
            raise RuntimeError("simulated send failure")
        await super().send_progress_notification(progress_token, progress_value, total=total, message=message)

    async def wait_for_send(self) -> None:
        """Wait until the emitter is blocked inside a send."""
        await self._started.wait()

    def release(self) -> None:
        """Let the held send finish; the next send will be held again."""
        gate = self._gate
        self._started = anyio.Event()
        self._gate = anyio.Event()
        gate.set()

    def stop_holding(self) -> None:
        """Release the held send, if any, and let all later sends through."""
        self._holding = False
        self.release()


_HELD_CONFIG = ProgressConfig(emit_hz=0, retry_backoff=(0.0, 0.0))


async def _stop_holding_once_blocked(session: HeldSession) -> None:
    """Release sends only once ``close()`` is waiting, so it runs while a state is in flight."""
    await anyio.wait_all_tasks_blocked()
    session.stop_holding()


@pytest.mark.anyio
async def test_close_while_send_in_flight_does_not_regress() -> None:
    """Deterministic version of the close race: the send of 4 is held while close() runs."""
    session = HeldSession()
    closes: list[ProgressCloseEvent] = []
    telemetry = ProgressTelemetry(on_close=lambda evt: closes.append(evt))

    async with with_request_context(token="tok", session=session), anyio.create_task_group() as tg:
        async with progress(total=4, telemetry=telemetry, config=_HELD_CONFIG) as tracker:
            await tracker.advance(1, "one")
            await session.wait_for_send()
            session.release()  # 1 delivered
            await tracker.set(4, message="done")
            await session.wait_for_send()  # 4 is in flight
            tg.start_soon(_stop_holding_once_blocked, session)

    assert [n.progress for n in session.notifications] == [1, 4]
    assert closes[-1].final_progress == 4
    assert closes[-1].final_message == "done"


@pytest.mark.anyio
async def test_advance_builds_on_held_in_flight_send() -> None:
    """Deterministic version of the advance race: the send of 3 is held while advance() runs."""
    session = HeldSession()

    async with with_request_context(token="tok", session=session):
        async with progress(total=10, config=_HELD_CONFIG) as tracker:
            await tracker.advance(1)
            await session.wait_for_send()
            session.release()  # 1 delivered
            await tracker.set(3)
            await session.wait_for_send()  # 3 is in flight
            try:
                assert await tracker.advance(1) == 4
            finally:
                session.stop_holding()

    _assert_monotonic(session.notifications)
    assert session.notifications[-1].progress == 4


@pytest.mark.anyio
async def test_close_during_retry_does_not_regress() -> None:
    """A state being retried after a failed send is still in flight; close() must not re-send an older one."""
    session = HeldSession(fail_attempts=(2,))

    async with with_request_context(token="tok", session=session), anyio.create_task_group() as tg:
        async with progress(total=4, config=_HELD_CONFIG) as tracker:
            await tracker.set(1)
            await session.wait_for_send()
            session.release()  # attempt 1: 1 delivered
            await tracker.set(4)
            await session.wait_for_send()
            session.release()  # attempt 2: sending 4 fails
            await session.wait_for_send()  # attempt 3: 4 is being retried
            tg.start_soon(_stop_holding_once_blocked, session)

    assert [n.progress for n in session.notifications] == [1, 4]
    assert session.attempts == 3


@pytest.mark.anyio
async def test_set_below_in_flight_value_raises() -> None:
    """Monotonicity is checked against the in-flight state, not just the last delivered one."""
    session = HeldSession()

    async with with_request_context(token="tok", session=session):
        async with progress(total=10, config=_HELD_CONFIG) as tracker:
            await tracker.set(1)
            await session.wait_for_send()
            session.release()  # 1 delivered
            await tracker.set(3)
            await session.wait_for_send()  # 3 is in flight
            try:
                with pytest.raises(ValueError):
                    await tracker.set(2)
            finally:
                session.stop_holding()

    _assert_monotonic(session.notifications)
    assert session.notifications[-1].progress == 3
