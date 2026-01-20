#!/usr/bin/env bash
# Integration test: runs all showcase examples
set -e

cd "$(dirname "$0")/../.."

cleanup() {
    echo "Cleaning up..."
    tmux kill-session -t showcase 2>/dev/null || true
    lsof -ti :8000 | xargs kill -9 2>/dev/null || true
    lsof -ti :8001 | xargs kill -9 2>/dev/null || true
}
trap cleanup EXIT

echo "========================================="
echo "Dedalus MCP Showcase Integration Tests"
echo "========================================="
echo ""

# Test 01: Minimal
echo "[01] Testing minimal server + client..."
tmux new-session -d -s showcase 'uv run python examples/showcase/01_minimal.py 2>&1'
sleep 3
uv run python examples/showcase/01_client.py 2>&1
tmux kill-session -t showcase
lsof -ti :8000 | xargs kill -9 2>/dev/null || true
echo "[01] ✓ Minimal test passed"
echo ""

# Test 02: Bidirectional
echo "[02] Testing bidirectional (sampling)..."
tmux new-session -d -s showcase 'uv run python examples/showcase/02_bidirectional_server.py 2>&1'
sleep 3
uv run python examples/showcase/02_bidirectional_client.py 2>&1
tmux kill-session -t showcase
lsof -ti :8000 | xargs kill -9 2>/dev/null || true
echo "[02] ✓ Bidirectional test passed"
echo ""

# Test 03: Real-time
echo "[03] Testing real-time tool updates..."
tmux new-session -d -s showcase 'uv run python examples/showcase/03_realtime_server.py 2>&1'
sleep 4
uv run python examples/showcase/03_realtime_client.py 2>&1
tmux kill-session -t showcase
lsof -ti :8000 | xargs kill -9 2>/dev/null || true
lsof -ti :8001 | xargs kill -9 2>/dev/null || true
echo "[03] ✓ Real-time test passed"
echo ""

echo "========================================="
echo "All showcase tests passed!"
echo "========================================="
