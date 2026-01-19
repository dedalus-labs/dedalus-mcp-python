# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""MCP server chaining: LLM → MCP → MCP → Client

This example demonstrates the POWER of MCP composability:

1. A mock "LLM" implemented as a FastAPI SSE streaming endpoint
2. An MCP server that wraps that LLM endpoint as a tool
3. A SECOND MCP server that uses the first as its sampling backend
4. A client that calls the second server, triggering the whole chain

Architecture:
```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  Client                                                         │
│    │                                                            │
│    │ call_tool("summarize")                                     │
│    ▼                                                            │
│  MCP Server B (:8001)                                           │
│    │  - Has tool "summarize"                                    │
│    │  - Needs LLM for reasoning                                 │
│    │                                                            │
│    │ request_sampling()                                         │
│    ▼                                                            │
│  MCP Client (inside Server B)                                   │
│    │                                                            │
│    │ call_tool("generate")                                      │
│    ▼                                                            │
│  MCP Server A (:8000)                                           │
│    │  - Has tool "generate"                                     │
│    │  - Wraps SSE LLM endpoint                                  │
│    │                                                            │
│    │ HTTP SSE                                                   │
│    ▼                                                            │
│  FastAPI SSE Endpoint (:8002)                                   │
│    - Mock LLM with streaming response                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

This is MCP at full power. Servers compose. Capabilities chain.

Usage:
    uv run python examples/advanced/llm_chain.py

Requires: pip install fastapi httpx-sse (or uv pip install)
"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager

import anyio
import httpx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import StreamingResponse
from starlette.routing import Route
import uvicorn

from dedalus_mcp import MCPServer, get_context, tool
from dedalus_mcp.client import MCPClient, ClientCapabilitiesConfig
from dedalus_mcp.types import CreateMessageRequestParams, CreateMessageResult, SamplingMessage, TextContent

# Suppress noise
for name in ("mcp", "httpx", "uvicorn", "uvicorn.access", "uvicorn.error"):
    logging.getLogger(name).setLevel(logging.WARNING)


# ============================================================================
# Layer 1: Mock LLM with FastAPI SSE Streaming
# ============================================================================


async def stream_llm_response(prompt: str):
    """Simulate LLM streaming response."""
    # Mock responses based on prompt content
    if "summarize" in prompt.lower():
        chunks = [
            "This ",
            "document ",
            "discusses ",
            "key ",
            "architectural ",
            "decisions ",
            "for ",
            "a ",
            "microservices ",
            "system.",
        ]
    elif "analyze" in prompt.lower():
        chunks = ["The ", "analysis ", "shows ", "positive ", "trends ", "in ", "all ", "key ", "metrics."]
    else:
        chunks = ["I ", "understand ", "your ", "request ", "and ", "have ", "processed ", "it."]

    for chunk in chunks:
        yield f"data: {json.dumps({'text': chunk})}\n\n"
        await asyncio.sleep(0.05)  # Simulate streaming delay

    yield "data: [DONE]\n\n"


async def llm_endpoint(request: Request) -> StreamingResponse:
    """FastAPI-style SSE endpoint for mock LLM."""
    body = await request.json()
    prompt = body.get("prompt", "")

    return StreamingResponse(stream_llm_response(prompt), media_type="text/event-stream")


llm_app = Starlette(routes=[Route("/v1/completions", llm_endpoint, methods=["POST"])])


# ============================================================================
# Layer 2: MCP Server A - Wraps LLM endpoint as a tool
# ============================================================================

server_a = MCPServer("llm-wrapper", instructions="I wrap an LLM streaming endpoint")


@tool(description="Generate text using the LLM")
async def generate(prompt: str, max_tokens: int = 100) -> dict:
    """Call the mock LLM endpoint and collect streamed response."""
    ctx = get_context()
    await ctx.info(f"Calling LLM with prompt: {prompt[:50]}...")

    full_response = ""

    async with httpx.AsyncClient() as client:
        async with client.stream("POST", "http://127.0.0.1:8002/v1/completions", json={"prompt": prompt}) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        full_response += chunk.get("text", "")
                    except json.JSONDecodeError:
                        pass

    await ctx.info(f"LLM response: {len(full_response)} chars")
    return {"response": full_response, "tokens_used": len(full_response.split())}


server_a.collect(generate)


# ============================================================================
# Layer 3: MCP Server B - Uses Server A as its "LLM" via MCP
# ============================================================================

server_b = MCPServer("reasoning-server", instructions="I use another MCP server for LLM capabilities")

# Connection to Server A (initialized at startup)
mcp_llm_client: MCPClient | None = None


@tool(description="Summarize text using chained MCP servers")
async def summarize(text: str) -> dict:
    """
    This tool:
    1. Receives request from client
    2. Calls Server A's "generate" tool for LLM reasoning
    3. Returns summarized result
    """
    ctx = get_context()
    await ctx.info("Summarizing via MCP chain...")

    if mcp_llm_client is None:
        return {"error": "LLM client not connected"}

    # Call Server A's generate tool
    result = await mcp_llm_client.call_tool(
        "generate", {"prompt": f"Summarize this text:\n\n{text}", "max_tokens": 100}
    )

    return {
        "original_length": len(text),
        "summary": result.structuredContent.get("response", ""),
        "chain": "Client → Server B → Server A → LLM SSE",
    }


@tool(description="Analyze text with multi-hop reasoning")
async def deep_analyze(text: str) -> dict:
    """
    Multi-hop analysis:
    1. First LLM call: Extract key points
    2. Second LLM call: Analyze the key points
    """
    ctx = get_context()

    if mcp_llm_client is None:
        return {"error": "LLM client not connected"}

    # Hop 1: Extract key points
    await ctx.info("Hop 1: Extracting key points...")
    hop1 = await mcp_llm_client.call_tool("generate", {"prompt": f"Extract key points from:\n\n{text}"})
    key_points = hop1.structuredContent.get("response", "")

    # Hop 2: Analyze the key points
    await ctx.info("Hop 2: Analyzing key points...")
    hop2 = await mcp_llm_client.call_tool("generate", {"prompt": f"Analyze these key points:\n\n{key_points}"})
    analysis = hop2.structuredContent.get("response", "")

    return {"key_points": key_points, "analysis": analysis, "hops": 2, "chain": "Client → B → A → LLM (×2)"}


server_b.collect(summarize, deep_analyze)


# ============================================================================
# Orchestration: Start all services
# ============================================================================


async def start_llm_service() -> None:
    """Start the mock LLM SSE endpoint on :8002."""
    config = uvicorn.Config(llm_app, host="127.0.0.1", port=8002, log_level="warning")
    server = uvicorn.Server(config)
    await server.serve()


async def start_server_a() -> None:
    """Start MCP Server A (LLM wrapper) on :8000."""
    await server_a.serve(port=8000)


async def start_server_b() -> None:
    """Start MCP Server B (reasoning) on :8001."""
    global mcp_llm_client

    # Wait for Server A to be ready
    await asyncio.sleep(2)

    # Connect to Server A as our LLM backend
    print("Server B connecting to Server A...")
    mcp_llm_client = await MCPClient.connect("http://127.0.0.1:8000/mcp")
    print(f"Server B connected to: {mcp_llm_client.initialize_result.serverInfo.name}")

    await server_b.serve(port=8001)


async def run_demo() -> None:
    """Run a demo client against the chain."""
    await asyncio.sleep(4)  # Wait for all services

    print("\n" + "=" * 60)
    print("DEMO: Client calling the MCP chain")
    print("=" * 60 + "\n")

    client = await MCPClient.connect("http://127.0.0.1:8001/mcp")
    print(f"Client connected to: {client.initialize_result.serverInfo.name}\n")

    # List tools
    tools = await client.list_tools()
    print(f"Available tools: {[t.name for t in tools.tools]}\n")

    # Call summarize (single hop through chain)
    print("--- Calling summarize (single hop) ---")
    text = (
        "MCP enables composable AI systems. Servers can be clients to other servers. This creates powerful pipelines."
    )
    result = await client.call_tool("summarize", {"text": text})
    print(f"Chain: {result.structuredContent.get('chain')}")
    print(f"Summary: {result.structuredContent.get('summary')}\n")

    # Call deep_analyze (multi-hop)
    print("--- Calling deep_analyze (multi-hop) ---")
    result = await client.call_tool("deep_analyze", {"text": text})
    print(f"Chain: {result.structuredContent.get('chain')}")
    print(f"Key Points: {result.structuredContent.get('key_points')}")
    print(f"Analysis: {result.structuredContent.get('analysis')}\n")

    await client.close()

    print("=" * 60)
    print("Demo complete! This showed:")
    print("  1. FastAPI SSE mock LLM (:8002)")
    print("  2. MCP Server A wrapping LLM as tool (:8000)")
    print("  3. MCP Server B using Server A for reasoning (:8001)")
    print("  4. Client calling Server B, triggering the whole chain")
    print("=" * 60)


async def main() -> None:
    print("=" * 60)
    print("MCP SERVER CHAINING: LLM → MCP → MCP → Client")
    print("=" * 60)
    print("\nStarting services:")
    print("  :8002 - Mock LLM (FastAPI SSE)")
    print("  :8000 - MCP Server A (LLM wrapper)")
    print("  :8001 - MCP Server B (reasoning server)")
    print("\nWatch the chain in action...\n")

    async with anyio.create_task_group() as tg:
        tg.start_soon(start_llm_service)
        tg.start_soon(start_server_a)
        tg.start_soon(start_server_b)
        tg.start_soon(run_demo)


if __name__ == "__main__":
    asyncio.run(main())
