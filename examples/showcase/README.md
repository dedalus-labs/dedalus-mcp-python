# Dedalus MCP Showcase

Working examples that demonstrate Dedalus MCP's capabilities. Each example is designed to be copy-pasted and run immediately.

## Quick Start

```bash
# Start any server
uv run python examples/showcase/01_minimal.py

# In another terminal, run its client
uv run python examples/showcase/01_client.py
```

## Examples

### 01: Minimal Server + Client

The absolute smallest working MCP setup. One tool, automatic schema inference, streamable HTTP transport.

```bash
uv run python examples/showcase/01_minimal.py    # Server
uv run python examples/showcase/01_client.py    # Client
```

**What it shows**: `@tool` decorator, `server.collect()`, `MCPClient.connect()`

### 02: Bidirectional Communication

Server that asks the client for LLM completions during tool execution. This is MCP's "sampling" capability.

```bash
uv run python examples/showcase/02_bidirectional_server.py
uv run python examples/showcase/02_bidirectional_client.py
```

**What it shows**: `ctx.sample()`, sampling handlers, multi-step tool execution

### 03: Real-Time Tool Updates

Add and remove tools at runtime. Connected clients see changes immediately via `notifications/tools/list_changed`.

```bash
uv run python examples/showcase/03_realtime_server.py
uv run python examples/showcase/03_realtime_client.py

# In a third terminal, manipulate tools:
curl -X POST http://127.0.0.1:8001/tools \
     -H "Content-Type: application/json" \
     -d '{"name": "greet", "description": "Say hello"}'
```

**What it shows**: Dynamic tool registration, `notify_tools_list_changed()`, control API pattern

### 04: Live Resources

Resources that update in real-time. Simulates a stock ticker and system metrics dashboard.

```bash
uv run python examples/showcase/04_live_resources_server.py
```

**What it shows**: `@resource` decorator, resource templates, `notify_resources_list_changed()`

### 05: Progress Reporting

Long-running tools that report progress back to the client.

```bash
uv run python examples/showcase/05_progress_server.py
```

**What it shows**: `ctx.progress()`, progress tokens, staged operations

## Running Integration Tests

Use tmux to run server and client together:

```bash
# Create session with two panes
tmux new-session -d -s mcp
tmux split-window -h

# Start server in left pane
tmux send-keys -t mcp:0.0 'uv run python examples/showcase/01_minimal.py' C-m

# Wait for server, then run client in right pane
sleep 2
tmux send-keys -t mcp:0.1 'uv run python examples/showcase/01_client.py' C-m

# Attach to watch
tmux attach -t mcp

# Clean up
tmux kill-session -t mcp
```

## What Dedalus MCP Supports

| Capability | Example |
|------------|---------|
| Tools | 01, 02, 03 |
| Resources | 04 |
| Prompts | See `examples/prompts/` |
| Progress | 05 |
| Sampling (bidirectional) | 02 |
| Elicitation (bidirectional) | See `examples/client/elicitation_handler.py` |
| Real-time notifications | 03, 04 |
| DPoP authentication | See `examples/client/dpop_auth.py` |
