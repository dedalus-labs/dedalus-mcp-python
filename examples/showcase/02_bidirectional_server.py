# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Server that asks the client for LLM completions.

MCP is bidirectional. This server demonstrates sampling: during tool
execution, the server requests an LLM completion from the client. The
client handles it (using any LLM provider) and returns the result.

This enables powerful patterns like:
- Agentic workflows where tools need reasoning
- Multi-step planning within a single tool call
- Dynamic prompting based on intermediate results

Usage:
    uv run python examples/showcase/02_bidirectional_server.py
"""

import asyncio
import logging
from dedalus_mcp import MCPServer, get_context, tool
from dedalus_mcp.types import CreateMessageRequestParams, SamplingMessage, TextContent

# Suppress log noise
for name in ("mcp", "httpx", "uvicorn", "uvicorn.access", "uvicorn.error"):
    logging.getLogger(name).setLevel(logging.WARNING)

server = MCPServer("bidirectional", instructions="I can ask you for LLM help mid-tool")


@tool(description="Analyze text sentiment using the connected LLM")
async def analyze_sentiment(text: str) -> dict:
    """Asks the client's LLM to analyze sentiment."""
    ctx = get_context()
    mcp_server = ctx.server
    if mcp_server is None:
        return {"error": "Server not available"}

    # Log progress
    await ctx.info(f"Analyzing: {text[:50]}...")

    # Server requests LLM completion from client via sampling
    params = CreateMessageRequestParams(
        messages=[
            SamplingMessage(
                role="user",
                content=TextContent(
                    type="text",
                    text=f"Analyze the sentiment of this text. Reply with just: positive, negative, or neutral.\n\nText: {text}",
                ),
            )
        ],
        maxTokens=10,
    )

    response = await mcp_server.request_sampling(params)
    sentiment = response.content.text.strip().lower()
    return {"text": text, "sentiment": sentiment, "model": response.model}


@tool(description="Summarize then expand on a topic")
async def summarize_and_expand(topic: str) -> dict:
    """Two-step reasoning: summarize, then expand."""
    ctx = get_context()
    mcp_server = ctx.server
    if mcp_server is None:
        return {"error": "Server not available"}

    # Step 1: Get summary
    await ctx.info("Step 1: Summarizing...")
    params1 = CreateMessageRequestParams(
        messages=[
            SamplingMessage(role="user", content=TextContent(type="text", text=f"Summarize '{topic}' in one sentence."))
        ],
        maxTokens=100,
    )
    summary_response = await mcp_server.request_sampling(params1)
    summary = summary_response.content.text

    # Step 2: Expand based on summary
    await ctx.info("Step 2: Expanding...")
    params2 = CreateMessageRequestParams(
        messages=[
            SamplingMessage(
                role="user",
                content=TextContent(
                    type="text",
                    text=f"Given this summary: '{summary}'\n\nNow provide three interesting facts about {topic}.",
                ),
            )
        ],
        maxTokens=300,
    )
    expansion_response = await mcp_server.request_sampling(params2)
    expansion = expansion_response.content.text

    return {"topic": topic, "summary": summary, "expansion": expansion}


server.collect(analyze_sentiment, summarize_and_expand)

if __name__ == "__main__":
    asyncio.run(server.serve())
