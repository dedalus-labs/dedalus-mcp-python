# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Server that requests LLM completions from the client.

MCP's sampling capability enables servers to ask clients for LLM
completions during tool execution. This is powerful for:

- Agentic workflows where tools need reasoning
- Multi-step planning within a single tool
- Dynamic prompting based on intermediate results
- Embedding AI capabilities in server-side logic

Usage:
    # Terminal 1:
    uv run python examples/capabilities/sampling/server.py

    # Terminal 2:
    uv run python examples/capabilities/sampling/client.py
"""

import asyncio
import logging

from dedalus_mcp import MCPServer, get_context, tool
from dedalus_mcp.types import CreateMessageRequestParams, SamplingMessage, TextContent

for name in ("mcp", "httpx", "uvicorn"):
    logging.getLogger(name).setLevel(logging.WARNING)

server = MCPServer("sampling-demo", instructions="I use the client's LLM for reasoning")


@tool(description="Analyze code and suggest improvements")
async def analyze_code(code: str, language: str = "python") -> dict:
    """Server asks client's LLM to analyze code."""
    ctx = get_context()
    mcp = ctx.server
    if not mcp:
        return {"error": "Server context not available"}

    await ctx.info(f"Analyzing {language} code...")

    params = CreateMessageRequestParams(
        messages=[
            SamplingMessage(
                role="user",
                content=TextContent(
                    type="text",
                    text=f"""Analyze this {language} code and provide:
1. A brief summary of what it does
2. Any bugs or issues
3. Suggestions for improvement

Code:
```{language}
{code}
```""",
                ),
            )
        ],
        maxTokens=500,
    )

    response = await mcp.request_sampling(params)
    return {"language": language, "analysis": response.content.text, "model": response.model}


@tool(description="Generate test cases for a function")
async def generate_tests(function_code: str, test_framework: str = "pytest") -> dict:
    """Server asks client's LLM to generate tests."""
    ctx = get_context()
    mcp = ctx.server
    if not mcp:
        return {"error": "Server context not available"}

    await ctx.info("Generating test cases...")

    params = CreateMessageRequestParams(
        messages=[
            SamplingMessage(
                role="user",
                content=TextContent(
                    type="text",
                    text=f"""Generate comprehensive {test_framework} test cases for this function.
Include edge cases and error conditions.

Function:
```python
{function_code}
```

Output only the test code, no explanations.""",
                ),
            )
        ],
        maxTokens=800,
    )

    response = await mcp.request_sampling(params)
    return {"framework": test_framework, "tests": response.content.text, "model": response.model}


@tool(description="Multi-step document analysis")
async def analyze_document(document: str) -> dict:
    """Multi-step analysis using multiple LLM calls."""
    ctx = get_context()
    mcp = ctx.server
    if not mcp:
        return {"error": "Server context not available"}

    results = {}

    # Step 1: Summarize
    await ctx.info("Step 1: Summarizing document...")
    summary_params = CreateMessageRequestParams(
        messages=[
            SamplingMessage(
                role="user",
                content=TextContent(type="text", text=f"Summarize this document in 2-3 sentences:\n\n{document}"),
            )
        ],
        maxTokens=150,
    )
    summary_response = await mcp.request_sampling(summary_params)
    results["summary"] = summary_response.content.text

    # Step 2: Extract key points
    await ctx.info("Step 2: Extracting key points...")
    points_params = CreateMessageRequestParams(
        messages=[
            SamplingMessage(
                role="user",
                content=TextContent(
                    type="text", text=f"List the 3-5 most important points from this document:\n\n{document}"
                ),
            )
        ],
        maxTokens=300,
    )
    points_response = await mcp.request_sampling(points_params)
    results["key_points"] = points_response.content.text

    # Step 3: Suggest actions
    await ctx.info("Step 3: Suggesting actions...")
    actions_params = CreateMessageRequestParams(
        messages=[
            SamplingMessage(
                role="user",
                content=TextContent(
                    type="text",
                    text=f"Based on this document, what actions should be taken?\n\nSummary: {results['summary']}\n\nDocument: {document[:500]}...",
                ),
            )
        ],
        maxTokens=200,
    )
    actions_response = await mcp.request_sampling(actions_params)
    results["suggested_actions"] = actions_response.content.text

    return results


server.collect(analyze_code, generate_tests, analyze_document)

if __name__ == "__main__":
    print("Sampling Demo Server: http://127.0.0.1:8000/mcp")
    print("\nTools that use client's LLM:")
    print("  analyze_code     - Code analysis with suggestions")
    print("  generate_tests   - Auto-generate test cases")
    print("  analyze_document - Multi-step document analysis")
    print("\nRun the client to see sampling in action!")
    asyncio.run(server.serve())
