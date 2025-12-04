"""
Test all SDK documentation examples against local dev server.
Run: uv run python test_sdk_examples.py
"""

import asyncio
import os

# Set environment before imports
os.environ["DEDALUS_API_KEY"] = "dsk_live_9b2ab766f0bf_f2deff57c5f266253e11d3a667d7017c"
os.environ["DEDALUS_BASE_URL"] = "http://localhost:8080"

from dedalus_labs import AsyncDedalus, Dedalus, DedalusRunner
from dedalus_labs.utils.stream import stream_async, stream_sync


# ============================================================================
# Test 1: Hello World (basic request)
# ============================================================================
async def test_hello_world():
    print("\n" + "="*60)
    print("TEST 1: Hello World")
    print("="*60)
    
    client = AsyncDedalus(base_url="http://localhost:8080")
    runner = DedalusRunner(client)

    response = await runner.run(
        input="What's the capital of France?",
        model="openai/gpt-4o-mini"
    )

    print(f"Response: {response.final_output}")
    return True


# ============================================================================
# Test 2: Local Tools
# ============================================================================
async def test_local_tools():
    print("\n" + "="*60)
    print("TEST 2: Local Tools")
    print("="*60)
    
    def add(a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

    def multiply(a: int, b: int) -> int:
        """Multiply two numbers."""
        return a * b

    client = AsyncDedalus(base_url="http://localhost:8080")
    runner = DedalusRunner(client)

    result = await runner.run(
        input="Calculate (15 + 27) * 2",
        model="openai/gpt-4o-mini",
        tools=[add, multiply]
    )

    print(f"Response: {result.final_output}")
    return True


# ============================================================================
# Test 3: Streaming (async)
# ============================================================================
async def test_streaming_async():
    print("\n" + "="*60)
    print("TEST 3: Streaming (async)")
    print("="*60)
    
    client = AsyncDedalus(base_url="http://localhost:8080")
    runner = DedalusRunner(client)

    result = runner.run(
        input="Count from 1 to 5.",
        model="openai/gpt-4o-mini",
        stream=True
    )

    await stream_async(result)
    print()  # newline after streaming
    return True


# ============================================================================
# Test 4: Sync Client
# ============================================================================
def test_sync_client():
    print("\n" + "="*60)
    print("TEST 4: Sync Client")
    print("="*60)
    
    client = Dedalus(base_url="http://localhost:8080")
    runner = DedalusRunner(client)

    response = runner.run(
        input="What's 2 + 2?",
        model="openai/gpt-4o-mini"
    )

    print(f"Response: {response.final_output}")
    return True


# ============================================================================
# Test 5: Tool with calculation
# ============================================================================
async def test_tip_calculator():
    print("\n" + "="*60)
    print("TEST 5: Tip Calculator Tool")
    print("="*60)
    
    def calculate_tip(amount: float, percentage: float = 18.0) -> float:
        """Calculate tip for a bill."""
        return amount * (percentage / 100)

    client = AsyncDedalus(base_url="http://localhost:8080")
    runner = DedalusRunner(client)

    result = await runner.run(
        input="What's a 20% tip on $85?",
        model="openai/gpt-4o-mini",
        tools=[calculate_tip]
    )

    print(f"Response: {result.final_output}")
    return True


# ============================================================================
# Test 6: MCP Server (web search) - may fail if server not available
# ============================================================================
async def test_mcp_server():
    print("\n" + "="*60)
    print("TEST 6: MCP Server (web search)")
    print("="*60)
    
    client = AsyncDedalus(base_url="http://localhost:8080")
    runner = DedalusRunner(client)

    try:
        result = await runner.run(
            input="What day is it today?",
            model="openai/gpt-4.1",
            mcp_servers=["tsion/brave-search-mcp"]
        )
        print(f"Response: {result.final_output}")
        return True
    except Exception as e:
        print(f"MCP test skipped (server may not be available): {e}")
        return None  # Not a failure, just skipped


# ============================================================================
# Test 7: Streaming with sync
# ============================================================================
def test_streaming_sync():
    print("\n" + "="*60)
    print("TEST 7: Streaming (sync)")
    print("="*60)
    
    client = Dedalus(base_url="http://localhost:8080")
    runner = DedalusRunner(client)

    result = runner.run(
        input="Say hello in 3 different languages.",
        model="openai/gpt-4o-mini",
        stream=True
    )

    stream_sync(result)
    print()  # newline after streaming
    return True


# ============================================================================
# Main runner
# ============================================================================
async def main():
    print("\n" + "#"*60)
    print("# SDK Documentation Examples Test Suite")
    print("# Server: http://localhost:8080")
    print("#"*60)
    
    results = {}
    
    # Async tests
    try:
        results["hello_world"] = await test_hello_world()
    except Exception as e:
        print(f"FAILED: {e}")
        results["hello_world"] = False

    try:
        results["local_tools"] = await test_local_tools()
    except Exception as e:
        print(f"FAILED: {e}")
        results["local_tools"] = False

    try:
        results["streaming_async"] = await test_streaming_async()
    except Exception as e:
        print(f"FAILED: {e}")
        results["streaming_async"] = False

    try:
        results["tip_calculator"] = await test_tip_calculator()
    except Exception as e:
        print(f"FAILED: {e}")
        results["tip_calculator"] = False

    try:
        results["mcp_server"] = await test_mcp_server()
    except Exception as e:
        print(f"FAILED: {e}")
        results["mcp_server"] = False

    # Sync tests
    try:
        results["sync_client"] = test_sync_client()
    except Exception as e:
        print(f"FAILED: {e}")
        results["sync_client"] = False

    try:
        results["streaming_sync"] = test_streaming_sync()
    except Exception as e:
        print(f"FAILED: {e}")
        results["streaming_sync"] = False

    # Summary
    print("\n" + "#"*60)
    print("# Test Results Summary")
    print("#"*60)
    
    passed = 0
    failed = 0
    skipped = 0
    
    for name, result in results.items():
        if result is True:
            status = "✓ PASS"
            passed += 1
        elif result is None:
            status = "○ SKIP"
            skipped += 1
        else:
            status = "✗ FAIL"
            failed += 1
        print(f"  {status}: {name}")
    
    print(f"\nTotal: {passed} passed, {failed} failed, {skipped} skipped")
    
    if failed > 0:
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())

