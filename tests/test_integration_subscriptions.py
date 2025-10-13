"""Integration tests for cross-transport resource subscriptions.

Currently marked as xfail/todo. These should spin up real STDIO and
Streamable HTTP transports to ensure notifications flow end-to-end under load.
"""

import pytest

pytestmark = pytest.mark.xfail(reason="TODO: implement transport-level integration for resource subscriptions")


@pytest.mark.anyio
async def test_stdio_subscription_end_to_end():
    """Spin up a stdio transport server and verify resource updates reach a real client."""
    raise pytest.SkipTest("TODO: implement stdio integration test")


@pytest.mark.anyio
async def test_streamable_http_subscription_end_to_end():
    """Spin up streamable HTTP server, subscribe with client, and assert notifications are delivered."""
    raise pytest.SkipTest("TODO: implement streamable HTTP integration test")
