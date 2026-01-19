# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Test resources capability, per MCP 2024-11-05.

Requirements tested:
- Resource definition requires uri, name
- resources/list supports pagination
- resources/read requires uri parameter
- ReadResourceResult requires contents array (TextResourceContents or BlobResourceContents)
- resources/subscribe and resources/unsubscribe for change notifications
- resources/updated notification for subscribed resources
- resources/list_changed notification when capability declared
"""

from __future__ import annotations

import pytest

from dedalus_mcp import types


@pytest.mark.anyio
async def test_resource_definition_2024_11_05() -> None:
    """Verify Resource structure matches 2024-11-05 schema."""
    # Per schema: requires uri, name. Optional: description, mimeType, annotations, size
    resource = types.Resource(
        uri="file:///example/data.txt", name="Example Data", description="Sample data file", mimeType="text/plain"
    )

    assert str(resource.uri) == "file:///example/data.txt"
    assert resource.name == "Example Data"
    assert resource.mimeType == "text/plain"


@pytest.mark.anyio
async def test_list_resources_request_2024_11_05() -> None:
    """Verify ListResourcesRequest supports pagination."""
    # Per schema: method = "resources/list", optional cursor
    request = types.ListResourcesRequest(params=types.PaginatedRequestParams(cursor="page-2"))

    assert request.method == "resources/list"
    assert request.params.cursor == "page-2"


@pytest.mark.anyio
async def test_list_resources_result_2024_11_05() -> None:
    """Verify ListResourcesResult structure."""
    # Per schema: requires resources array, optional nextCursor
    result = types.ListResourcesResult(
        resources=[types.Resource(uri="file:///test.txt", name="Test")], nextCursor="next-page"
    )

    assert len(result.resources) == 1
    assert str(result.resources[0].uri) == "file:///test.txt"
    assert result.nextCursor == "next-page"


@pytest.mark.anyio
async def test_read_resource_request_2024_11_05() -> None:
    """Verify ReadResourceRequest structure."""
    # Per schema: method = "resources/read", params requires uri
    request = types.ReadResourceRequest(params=types.ReadResourceRequestParams(uri="file:///example.txt"))

    assert request.method == "resources/read"
    assert str(request.params.uri) == "file:///example.txt"


@pytest.mark.anyio
async def test_read_resource_result_text_2024_11_05() -> None:
    """Verify ReadResourceResult with TextResourceContents."""
    # Per schema: requires contents array of TextResourceContents | BlobResourceContents
    # TextResourceContents requires uri, text
    result = types.ReadResourceResult(
        contents=[
            types.TextResourceContents(uri="file:///example.txt", text="File contents here", mimeType="text/plain")
        ]
    )

    assert len(result.contents) == 1
    content = result.contents[0]
    assert isinstance(content, types.TextResourceContents)
    assert str(content.uri) == "file:///example.txt"
    assert content.text == "File contents here"


@pytest.mark.anyio
async def test_read_resource_result_blob_2024_11_05() -> None:
    """Verify ReadResourceResult with BlobResourceContents."""
    # Per schema: BlobResourceContents requires uri, blob (base64-encoded)
    import base64

    binary_data = b"Binary data here"
    encoded = base64.b64encode(binary_data).decode("utf-8")

    result = types.ReadResourceResult(
        contents=[types.BlobResourceContents(uri="file:///image.png", blob=encoded, mimeType="image/png")]
    )

    content = result.contents[0]
    assert isinstance(content, types.BlobResourceContents)
    assert content.blob == encoded
    assert base64.b64decode(content.blob) == binary_data


@pytest.mark.anyio
async def test_subscribe_request_2024_11_05() -> None:
    """Verify SubscribeRequest structure."""
    # Per schema: method = "resources/subscribe", params requires uri
    request = types.SubscribeRequest(params=types.SubscribeRequestParams(uri="file:///watch.txt"))

    assert request.method == "resources/subscribe"
    assert str(request.params.uri) == "file:///watch.txt"


@pytest.mark.anyio
async def test_unsubscribe_request_2024_11_05() -> None:
    """Verify UnsubscribeRequest structure."""
    # Per schema: method = "resources/unsubscribe", params requires uri
    request = types.UnsubscribeRequest(params=types.UnsubscribeRequestParams(uri="file:///watch.txt"))

    assert request.method == "resources/unsubscribe"
    assert str(request.params.uri) == "file:///watch.txt"


@pytest.mark.anyio
async def test_resource_updated_notification_2024_11_05() -> None:
    """Verify ResourceUpdatedNotification structure."""
    # Per schema: method = "notifications/resources/updated", params requires uri
    notification = types.ResourceUpdatedNotification(
        params=types.ResourceUpdatedNotificationParams(uri="file:///changed.txt")
    )

    assert notification.method == "notifications/resources/updated"
    assert str(notification.params.uri) == "file:///changed.txt"


@pytest.mark.anyio
async def test_resource_list_changed_notification_2024_11_05() -> None:
    """Verify ResourceListChangedNotification structure."""
    # Per schema: method = "notifications/resources/list_changed"
    notification = types.ResourceListChangedNotification(params=None)

    assert notification.method == "notifications/resources/list_changed"
