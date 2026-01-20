# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Client that provides LLM completions to the server.

When the server calls `server.request_sampling()`, this client receives
the request and fulfills it. This example uses a mock LLM, but you'd
plug in OpenAI, Anthropic, or any provider.

Usage:
    # Terminal 1: Start the server
    uv run python examples/showcase/02_bidirectional_server.py

    # Terminal 2: Run this client
    uv run python examples/showcase/02_bidirectional_client.py
"""

import asyncio
import logging

from dedalus_mcp.client import ClientCapabilitiesConfig, MCPClient
from dedalus_mcp.types import CreateMessageResult, TextContent


# Suppress log noise
for name in ("mcp", "httpx"):
    logging.getLogger(name).setLevel(logging.WARNING)


async def mock_llm(messages: list, max_tokens: int) -> str:
    """Mock LLM that returns canned responses. Replace with real provider."""
    content = ""
    if messages:
        msg = messages[-1]
        if hasattr(msg, "content"):
            c = msg.content
            content = c.text if hasattr(c, "text") else str(c)
        elif isinstance(msg, dict):
            content = msg.get("content", "")

    content_lower = content.lower()

    if "sentiment" in content_lower:
        return "positive"
    if "summarize" in content_lower:
        return "A brief overview of the key concepts."
    if "facts" in content_lower:
        return "1. Interesting fact one.\n2. Interesting fact two.\n3. Interesting fact three."
    return "I understand your request."


async def sampling_handler(context, params) -> CreateMessageResult:
    """Handle sampling requests from the server."""
    # Call mock LLM
    response_text = await mock_llm(params.messages, params.maxTokens or 100)

    return CreateMessageResult(
        role="assistant",
        content=TextContent(type="text", text=response_text),
        model="mock-llm-1.0",
        stopReason="endTurn",
    )


async def main() -> None:
    # Configure client to handle sampling requests
    config = ClientCapabilitiesConfig(sampling=sampling_handler)

    print("Connecting to bidirectional MCP server...")
    client = await MCPClient.connect("http://127.0.0.1:8000/mcp", capabilities=config)

    print(f"Connected to: {client.initialize_result.serverInfo.name}")
    print("This client provides LLM completions to the server.\n")

    # Call a tool that uses sampling
    print("Calling analyze_sentiment('I love this product! It is amazing!')...")
    result = await client.call_tool("analyze_sentiment", {"text": "I love this product! It is amazing!"})
    print(f"Result: {result.structuredContent}\n")

    # Call multi-step tool
    print("Calling summarize_and_expand('quantum computing')...")
    result = await client.call_tool("summarize_and_expand", {"topic": "quantum computing"})
    print(f"Result: {result.structuredContent}")

    await client.close()
    print("\nDemo complete!")


if __name__ == "__main__":
    asyncio.run(main())
