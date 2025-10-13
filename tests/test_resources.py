"""Resource capability tests following the MCP spec receipts.

See ``docs/mcp/spec/schema-reference/resources-read.md`` for the binary encoding
rules and ``resources-subscribe.md`` for subscription capability toggles.
"""

from __future__ import annotations

import base64
import gc
import weakref
from itertools import count

import anyio
import pytest

from openmcp import MCPServer, resource, types

from mcp.server.lowlevel.server import request_ctx
from mcp.shared.context import RequestContext


_request_counter = count(1)


class DummySession:
    def __init__(self, name: str = "session") -> None:
        self.notifications: list[types.ServerNotification] = []
        self.name = name

    async def send_notification(
        self,
        notification: types.ServerNotification,
        related_request_id: types.RequestId | None = None,
    ) -> None:
        await anyio.lowlevel.checkpoint()
        self.notifications.append(notification)


class FailingSession(DummySession):
    def __init__(self, name: str = "failing") -> None:
        super().__init__(name)
        self.failures = 0

    async def send_notification(
        self,
        notification: types.ServerNotification,
        related_request_id: types.RequestId | None = None,
    ) -> None:
        self.failures += 1
        raise RuntimeError("notification failure")


async def _run_with_context(session: DummySession, func, *args):
    ctx = RequestContext(
        request_id=next(_request_counter),
        meta=None,
        session=session,  # type: ignore[arg-type]
        lifespan_context={},
    )
    token = request_ctx.set(ctx)
    try:
        return await func(*args)
    finally:
        request_ctx.reset(token)


@pytest.mark.asyncio
async def test_resource_registration_and_read():
    server = MCPServer("resources-demo")

    with server.collecting():
        @resource("resource://demo/greeting", name="greeting", description="Simple greeting")
        def greeting() -> str:
            return "hello world"

    listed = await server.invoke_resource("resource://demo/greeting")
    assert listed.contents
    content = listed.contents[0]
    assert content.text == "hello world"
    assert content.mimeType == "text/plain"

    resources = server.register_resource(greeting)  # should be idempotent
    assert resources.uri == "resource://demo/greeting"

    listed_resources = await server.invoke_resource("resource://demo/greeting")
    assert listed_resources.contents[0].text == "hello world"


@pytest.mark.anyio
async def test_resource_subscription_emits_updates():
    server = MCPServer("resources-subscribe")
    session = DummySession()
    await _run_with_context(session, server._handle_resource_subscribe, "resource://demo/file")

    await server.notify_resource_updated("resource://demo/file")

    assert len(session.notifications) == 1
    notification = session.notifications[0]
    assert notification.root.method == "notifications/resources/updated"
    assert str(notification.root.params.uri) == "resource://demo/file"


@pytest.mark.anyio
async def test_resource_unsubscribe_stops_notifications():
    server = MCPServer("resources-unsubscribe")
    session = DummySession()
    await _run_with_context(session, server._handle_resource_subscribe, "resource://demo/file")
    await _run_with_context(session, server._handle_resource_unsubscribe, "resource://demo/file")

    await server.notify_resource_updated("resource://demo/file")
    assert session.notifications == []


@pytest.mark.anyio
async def test_resource_subscribe_capability_advertised():
    server = MCPServer("resources-capability-flag")
    options = server.create_initialization_options()
    assert options.capabilities.resources
    assert options.capabilities.resources.subscribe is True


@pytest.mark.asyncio
async def test_resource_binary_content_encoding():
    """Binary resources must surface as base64 blobs per the spec.

    Read more: https://modelcontextprotocol.io/specification/2025-06-18/schema#blobresourcecontents

    """
    payload = b"\x00\x01\x02demo"
    server = MCPServer("resources-binary")

    with server.collecting():
        @resource("resource://demo/binary", mime_type="application/octet-stream")
        def binary() -> bytes:
            return payload

    result = await server.invoke_resource("resource://demo/binary")
    assert result.contents
    blob = result.contents[0]
    assert isinstance(blob, types.BlobResourceContents)
    assert blob.mimeType == "application/octet-stream"
    assert base64.b64decode(blob.blob) == payload


def test_resource_subscribe_capability_flag():
    """`resources.subscribe` is advertised by default and remains enabled after overrides."""

    server = MCPServer("resources-capability")
    init_opts = server.create_initialization_options()
    assert init_opts.capabilities.resources
    assert init_opts.capabilities.resources.subscribe is True

    @server.subscribe_resource()
    async def _sub(uri: str) -> None:  # pragma: no cover
        return None

    @server.unsubscribe_resource()
    async def _unsub(uri: str) -> None:  # pragma: no cover
        return None

    updated_opts = server.create_initialization_options()
    assert updated_opts.capabilities.resources
    assert updated_opts.capabilities.resources.subscribe is True


@pytest.mark.anyio
async def test_resource_subscription_duplicate_registration():
    server = MCPServer("resources-duplicate")
    session = DummySession("dup")
    uri = "resource://demo/dup"

    await _run_with_context(session, server._handle_resource_subscribe, uri)
    await _run_with_context(session, server._handle_resource_subscribe, uri)

    await server.notify_resource_updated(uri)
    assert len(session.notifications) == 1

    async with server._resource_subscription_lock:
        subscribers = list(server._resource_subscribers.get(uri, ()))
    assert len(subscribers) == 1


@pytest.mark.anyio
async def test_resource_subscription_garbage_collection_cleanup():
    server = MCPServer("resources-gc")
    uri = "resource://demo/gc"
    session = DummySession("gc")
    await _run_with_context(session, server._handle_resource_subscribe, uri)

    session_ref = weakref.ref(session)
    session = None  # drop strong reference
    gc.collect()
    await anyio.sleep(0)

    await server.notify_resource_updated(uri)

    async with server._resource_subscription_lock:
        subscribers = server._resource_subscribers.get(uri)
        remaining = 0 if subscribers is None else len(list(subscribers))
    assert session_ref() is None
    assert remaining == 0


@pytest.mark.anyio
async def test_resource_subscription_high_volume_notifications():
    server = MCPServer("resources-volume")
    uri = "resource://demo/high"
    sessions = [DummySession(f"vol-{i}") for i in range(50)]

    async with anyio.create_task_group() as tg:
        for session in sessions:
            tg.start_soon(_run_with_context, session, server._handle_resource_subscribe, uri)

    await server.notify_resource_updated(uri)
    for session in sessions:
        assert len(session.notifications) == 1

    await server.notify_resource_updated(uri)
    for session in sessions:
        assert len(session.notifications) == 2


@pytest.mark.anyio
async def test_resource_subscription_concurrent_activity():
    server = MCPServer("resources-concurrent")
    uri = "resource://demo/concurrent"
    sessions = [DummySession(f"conc-{i}") for i in range(10)]

    async def worker(session: DummySession) -> None:
        for _ in range(5):
            await _run_with_context(session, server._handle_resource_subscribe, uri)
            await server.notify_resource_updated(uri)
            await _run_with_context(session, server._handle_resource_unsubscribe, uri)

    async with anyio.create_task_group() as tg:
        for session in sessions:
            tg.start_soon(worker, session)

    max_expected = len(sessions) * 5
    for session in sessions:
        assert 0 < len(session.notifications) <= max_expected

    async with server._resource_subscription_lock:
        assert not server._resource_subscribers.get(uri)


@pytest.mark.anyio
async def test_resource_subscription_failed_session_cleanup():
    server = MCPServer("resources-failing")
    uri = "resource://demo/failing"
    session = FailingSession()

    await _run_with_context(session, server._handle_resource_subscribe, uri)
    await server.notify_resource_updated(uri)

    async with server._resource_subscription_lock:
        subscribers = server._resource_subscribers.get(uri)
        remaining = 0 if subscribers is None else len(list(subscribers))

    assert session.failures == 1
    assert remaining == 0
