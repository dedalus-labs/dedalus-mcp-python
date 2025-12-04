# Client Examples

Examples demonstrating client-side MCP capabilities. All examples are self-contained and runnable.

## Connection & Auth

### basic_connect.py
Script-style client connection without context managers. The primary API for most applications.

```python
client = await MCPClient.connect("http://localhost:8000/mcp")
tools = await client.list_tools()
await client.close()
```

### dpop_auth.py
RFC 9449 DPoP authentication for sender-constrained tokens. Required for Dedalus MCP servers.

```python
auth = DPoPAuth(access_token="...", dpop_key=ec_private_key)
client = await MCPClient.connect(url, auth=auth)
```

### bearer_auth.py
Simple OAuth Bearer token auth for standard protected servers.

```python
auth = BearerAuth(access_token="...")
client = await MCPClient.connect(url, auth=auth)
```

## Capability Handlers

### sampling_handler.py (99 LOC)
Demonstrates client handling of `sampling/createMessage` requests from servers. Integrates with the Anthropic API to provide real LLM completions when servers need them during tool execution.

**Key concepts**:
- Handler signature: `async def sampling_handler(context, params) -> CreateMessageResult | ErrorData`
- Message format conversion (MCP ↔ Anthropic)
- Model preference negotiation
- Error handling without crashing the connection

**Spec**: https://modelcontextprotocol.io/specification/2025-06-18/client/sampling

### elicitation_handler.py (138 LOC)
Demonstrates client handling of `elicitation/create` requests from servers. Uses CLI prompts to collect user input matching a JSON schema.

**Key concepts**:
- Schema-driven input collection
- Type coercion (boolean, integer, number, string)
- Three-way actions (accept, decline, cancel)
- Required vs optional field handling

**Spec**: https://modelcontextprotocol.io/specification/2025-06-18/client/elicitation

### roots_config.py (95 LOC)
Demonstrates client advertising filesystem roots to establish security boundaries. Shows both initial configuration and dynamic updates.

**Key concepts**:
- file:// URI construction (cross-platform)
- Initial roots via `ClientCapabilitiesConfig`
- Dynamic updates with `client.update_roots()`
- `notifications/roots/list_changed` broadcasting

**Spec**: https://modelcontextprotocol.io/specification/2025-06-18/client/roots

### full_capabilities.py (153 LOC)
Combines all client capabilities (sampling, elicitation, roots, logging) into a single production-ready client configuration.

**Key concepts**:
- Multiple capability handlers in one client
- Capability negotiation during initialization
- Logging notifications from servers
- Complete client setup pattern

## Running the Examples

### Connection examples

```bash
# Start a server first
uv run python examples/tools/basic_tool.py

# In another terminal
uv run python examples/client/basic_connect.py
```

### Auth examples

Auth examples require a protected server and valid tokens. Update the constants before running:

```bash
uv run python examples/client/bearer_auth.py
uv run python examples/client/dpop_auth.py
```

### Capability handler examples

All require a running MCP server at `http://127.0.0.1:8000/mcp`.

```bash
# For sampling (requires Anthropic API key)
export ANTHROPIC_API_KEY=your-key
uv run python examples/client/sampling_handler.py

# For other handlers
uv run python examples/client/elicitation_handler.py
uv run python examples/client/roots_config.py
uv run python examples/client/full_capabilities.py
```

## See Also

- [Sampling documentation](../../docs/openmcp/sampling.md)
- [Elicitation documentation](../../docs/openmcp/elicitation.md)
- [Roots documentation](../../docs/openmcp/roots.md)
- [Full demo client](../full_demo/simple_client.py)
