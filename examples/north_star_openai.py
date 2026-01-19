#!/usr/bin/env python3
# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""
North Star: OpenAI MCP Server

Wraps OpenAI API as MCP tools, demonstrating:
- Connection/Credential pattern for API key management
- ctx.dispatch() for authenticated HTTP requests
- LLM-as-a-tool pattern (MCP server that calls another LLM)

Usage:
    export OPENAI_API_KEY="sk-..."
    python examples/north_star_openai.py
"""

from __future__ import annotations

import asyncio
import os

from dedalus_mcp import HttpMethod, HttpRequest, MCPServer, get_context, tool
from dedalus_mcp.auth import Connection, Credential, Credentials

# ---------------------------------------------------------------------------
# 1. Define OpenAI connection
# ---------------------------------------------------------------------------

openai = Connection(
    "openai",
    credentials=Credentials(api_key="OPENAI_API_KEY"),
    base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
)

# ---------------------------------------------------------------------------
# 2. Define server and tools
# ---------------------------------------------------------------------------

server = MCPServer(name="openai-tools", connections=[openai])


@tool(description="Generate text using GPT-4o-mini")
async def generate_text(prompt: str, max_tokens: int = 500, temperature: float = 0.7) -> dict:
    """Generate text completion using OpenAI GPT-4o-mini.

    Args:
        prompt: The prompt to send to the model
        max_tokens: Maximum tokens to generate (default 500)
        temperature: Sampling temperature 0-2 (default 0.7)
    """
    ctx = get_context()
    response = await ctx.dispatch(
        HttpRequest(
            method=HttpMethod.POST,
            path="/chat/completions",
            body={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
        )
    )
    if response.success:
        data = response.response.body
        return {
            "text": data["choices"][0]["message"]["content"],
            "model": data["model"],
            "usage": data.get("usage", {}),
        }
    return {"error": response.error.message if response.error else "Generation failed"}


@tool(description="Generate embeddings for text")
async def generate_embeddings(text: str) -> dict:
    """Generate vector embeddings using text-embedding-3-small.

    Args:
        text: Text to embed (max ~8000 tokens)
    """
    ctx = get_context()
    response = await ctx.dispatch(
        HttpRequest(method=HttpMethod.POST, path="/embeddings", body={"model": "text-embedding-3-small", "input": text})
    )
    if response.success:
        data = response.response.body
        embedding = data["data"][0]["embedding"]
        return {
            "dimensions": len(embedding),
            "embedding_preview": embedding[:5],  # First 5 values
            "model": data["model"],
            "usage": data.get("usage", {}),
        }
    return {"error": response.error.message if response.error else "Embedding failed"}


@tool(description="List available OpenAI models")
async def list_models() -> list[dict]:
    """List all available OpenAI models."""
    ctx = get_context()
    response = await ctx.dispatch(HttpRequest(method=HttpMethod.GET, path="/models"))
    if response.success:
        models = response.response.body.get("data", [])
        # Return simplified model info, sorted by ID
        return sorted(
            [{"id": m["id"], "owned_by": m.get("owned_by", "unknown")} for m in models], key=lambda x: x["id"]
        )
    return [{"error": response.error.message if response.error else "List failed"}]


@tool(description="Analyze sentiment of text")
async def analyze_sentiment(text: str) -> dict:
    """Analyze sentiment using GPT-4o-mini.

    Args:
        text: Text to analyze for sentiment
    """
    ctx = get_context()
    response = await ctx.dispatch(
        HttpRequest(
            method=HttpMethod.POST,
            path="/chat/completions",
            body={
                "model": "gpt-4o-mini",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a sentiment analysis assistant. Respond with JSON containing: sentiment (positive/negative/neutral), confidence (0-1), and brief explanation.",
                    },
                    {"role": "user", "content": f"Analyze sentiment: {text}"},
                ],
                "max_tokens": 150,
                "temperature": 0,
                "response_format": {"type": "json_object"},
            },
        )
    )
    if response.success:
        import json

        content = response.response.body["choices"][0]["message"]["content"]
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {"raw_response": content}
    return {"error": response.error.message if response.error else "Analysis failed"}


@tool(description="Summarize long text")
async def summarize(text: str, style: str = "brief") -> dict:
    """Summarize text using GPT-4o-mini.

    Args:
        text: Text to summarize
        style: 'brief' (1-2 sentences), 'detailed' (paragraph), or 'bullets'
    """
    style_prompts = {
        "brief": "Provide a 1-2 sentence summary.",
        "detailed": "Provide a detailed paragraph summary.",
        "bullets": "Provide a bullet-point summary with 3-5 key points.",
    }

    ctx = get_context()
    response = await ctx.dispatch(
        HttpRequest(
            method=HttpMethod.POST,
            path="/chat/completions",
            body={
                "model": "gpt-4o-mini",
                "messages": [
                    {
                        "role": "system",
                        "content": f"You are a summarization assistant. {style_prompts.get(style, style_prompts['brief'])}",
                    },
                    {"role": "user", "content": f"Summarize this text:\n\n{text}"},
                ],
                "max_tokens": 300,
                "temperature": 0.3,
            },
        )
    )
    if response.success:
        return {
            "summary": response.response.body["choices"][0]["message"]["content"],
            "style": style,
            "usage": response.response.body.get("usage", {}),
        }
    return {"error": response.error.message if response.error else "Summarization failed"}


server.collect(generate_text, generate_embeddings, list_models, analyze_sentiment, summarize)

# ---------------------------------------------------------------------------
# 3. SDK initialization
# ---------------------------------------------------------------------------


async def main():
    api_key = os.environ.get("OPENAI_API_KEY")

    if not api_key:
        print("Set OPENAI_API_KEY environment variable")
        return

    # Bind credential to connection
    openai_cred = Credential(openai, api_key=api_key)

    print(f"Server: {server.name}")
    print(f"Tools: {server.tool_names}")
    print(f"Connections: {list(server.connections.keys())}")
    print(f"Base URL: {openai.base_url}")

    # ---------------------------------------------------------------------------
    # Full flow (when AS/Enclave are running):
    #
    #   from dedalus_labs import Dedalus
    #
    #   client = Dedalus(
    #       api_key="dsk_xxx",
    #       mcp_servers=[server],
    #       credentials=[openai_cred],
    #   )
    #
    #   response = await client.chat.completions.create(
    #       model="gpt-4",
    #       messages=[{"role": "user", "content": "Summarize the benefits of MCP"}],
    #   )
    # ---------------------------------------------------------------------------

    print("\nReady for AS/Enclave integration")


if __name__ == "__main__":
    asyncio.run(main())
