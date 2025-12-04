# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Tests for MCPServer.url property."""

from __future__ import annotations

import asyncio

import pytest

from dedalus_mcp import MCPServer, tool


@tool(description="Test tool")
def dummy_tool() -> str:
    return "ok"


# --- MCPServer.url property --------------------------------------------------


class TestMCPServerURL:
    """The url property enables external frameworks to discover serving endpoints."""

    def test_url_is_none_before_serve(self) -> None:
        """URL is None when server hasn't started."""
        server = MCPServer("test-server")
        assert server.url is None

    @pytest.mark.asyncio
    async def test_url_set_during_serve(self) -> None:
        """URL is set while server is serving."""
        server = MCPServer("test-server")
        server.collect(dummy_tool)

        serve_task = asyncio.create_task(server.serve(host="127.0.0.1", port=18765, verbose=False))
        await asyncio.sleep(0.3)

        try:
            assert server.url == "http://127.0.0.1:18765/mcp"
        finally:
            await server.shutdown()
            serve_task.cancel()
            try:
                await serve_task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_url_cleared_after_shutdown(self) -> None:
        """URL is None after server stops."""
        server = MCPServer("test-server")
        server.collect(dummy_tool)

        serve_task = asyncio.create_task(server.serve(host="127.0.0.1", port=18766, verbose=False))
        await asyncio.sleep(0.3)
        assert server.url is not None

        await server.shutdown()
        serve_task.cancel()
        try:
            await serve_task
        except asyncio.CancelledError:
            pass

        await asyncio.sleep(0.1)
        assert server.url is None

    def test_url_reflects_custom_port(self) -> None:
        """Custom port appears in URL."""
        server = MCPServer("test-server")
        server._serving_url = "http://127.0.0.1:9999/mcp"
        assert server.url == "http://127.0.0.1:9999/mcp"

    def test_url_reflects_custom_path(self) -> None:
        """Custom path appears in URL."""
        server = MCPServer("test-server")
        server._serving_url = "http://localhost:8000/custom/mcp"
        assert server.url == "http://localhost:8000/custom/mcp"
