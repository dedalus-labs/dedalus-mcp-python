# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Client that provides LLM completions to the server.

When the server calls `server.request_sampling()`, this client
receives the request and fulfills it using an LLM provider.

This example uses a mock LLM. In production, plug in:
- OpenAI: openai.chat.completions.create()
- Anthropic: anthropic.messages.create()
- Local models: ollama, llama.cpp, etc.

Usage:
    # Terminal 1:
    uv run python examples/capabilities/sampling/server.py

    # Terminal 2:
    uv run python examples/capabilities/sampling/client.py
"""

import asyncio
import logging

from dedalus_mcp.client import MCPClient, ClientCapabilitiesConfig
from dedalus_mcp.types import CreateMessageResult, TextContent

for name in ("mcp", "httpx"):
    logging.getLogger(name).setLevel(logging.WARNING)


# ============================================================================
# LLM Provider (mock — replace with real provider)
# ============================================================================


async def call_llm(messages: list, max_tokens: int) -> str:
    """Mock LLM that returns plausible responses.

    Replace with your actual LLM provider:

    # OpenAI
    response = await openai.chat.completions.create(
        model="gpt-4",
        messages=[{"role": m.role, "content": m.content.text} for m in messages],
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content

    # Anthropic
    response = await anthropic.messages.create(
        model="claude-3-sonnet",
        messages=[{"role": m.role, "content": m.content.text} for m in messages],
        max_tokens=max_tokens,
    )
    return response.content[0].text
    """
    # Extract the user's request
    user_msg = messages[-1].content.text if messages else ""
    user_lower = user_msg.lower()

    # Mock responses based on content
    if "analyze" in user_lower and "code" in user_lower:
        return """**Summary**: This code implements a basic function.

**Issues Found**:
- No input validation
- Missing docstring
- Could use type hints

**Suggestions**:
1. Add parameter validation
2. Include comprehensive docstring
3. Consider edge cases"""

    elif "test" in user_lower:
        return """```python
import pytest

def test_basic_case():
    assert function(1, 2) == 3

def test_edge_case_zero():
    assert function(0, 0) == 0

def test_negative_numbers():
    assert function(-1, 1) == 0

def test_large_numbers():
    assert function(1000000, 1000000) == 2000000
```"""

    elif "summarize" in user_lower:
        return "This document outlines key technical decisions and their rationale for the project architecture."

    elif "important points" in user_lower or "key points" in user_lower:
        return """1. Architecture follows microservices pattern
2. Database uses PostgreSQL with read replicas
3. Caching layer reduces latency by 60%
4. CI/CD pipeline ensures deployment safety"""

    elif "action" in user_lower:
        return """1. Schedule architecture review meeting
2. Set up monitoring dashboards
3. Document deployment procedures
4. Plan capacity for expected growth"""

    return "I understand your request and have processed it accordingly."


# ============================================================================
# Sampling Handler
# ============================================================================


async def sampling_handler(context, params) -> CreateMessageResult:
    """Handle sampling requests from the server."""
    print(f"\n[Sampling Request] maxTokens={params.maxTokens}")

    # Call your LLM provider
    response_text = await call_llm(params.messages, params.maxTokens or 500)

    print(f"[Sampling Response] {len(response_text)} chars")

    return CreateMessageResult(
        role="assistant",
        content=TextContent(type="text", text=response_text),
        model="mock-llm-1.0",  # Replace with actual model name
        stopReason="endTurn",
    )


# ============================================================================
# Main
# ============================================================================


async def main() -> None:
    config = ClientCapabilitiesConfig(sampling=sampling_handler)

    print("Connecting to sampling demo server...")
    client = await MCPClient.connect("http://127.0.0.1:8000/mcp", capabilities=config)

    print(f"Connected to: {client.initialize_result.serverInfo.name}")
    print("This client provides LLM completions to the server.\n")

    # Demo 1: Code analysis
    print("=" * 50)
    print("Demo 1: Code Analysis")
    print("=" * 50)

    code = """
def calculate_total(items):
    total = 0
    for item in items:
        total += item.price * item.quantity
    return total
"""
    result = await client.call_tool("analyze_code", {"code": code, "language": "python"})
    print(f"Analysis:\n{result.structuredContent['analysis']}\n")

    # Demo 2: Test generation
    print("=" * 50)
    print("Demo 2: Test Generation")
    print("=" * 50)

    func = """
def add(a: int, b: int) -> int:
    return a + b
"""
    result = await client.call_tool("generate_tests", {"function_code": func})
    print(f"Generated Tests:\n{result.structuredContent['tests']}\n")

    # Demo 3: Multi-step document analysis
    print("=" * 50)
    print("Demo 3: Multi-step Document Analysis")
    print("=" * 50)

    document = """
The new microservices architecture has been approved. Key decisions include:
using PostgreSQL for persistence, Redis for caching, and Kubernetes for
orchestration. The expected performance improvement is 60% reduction in
latency. Migration will begin Q1 next year.
"""
    result = await client.call_tool("analyze_document", {"document": document})
    print(f"Summary: {result.structuredContent['summary']}")
    print(f"\nKey Points:\n{result.structuredContent['key_points']}")
    print(f"\nActions:\n{result.structuredContent['suggested_actions']}")

    await client.close()
    print("\n" + "=" * 50)
    print("Demo complete!")


if __name__ == "__main__":
    asyncio.run(main())

