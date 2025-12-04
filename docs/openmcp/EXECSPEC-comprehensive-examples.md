# EXECSPEC: Comprehensive Examples & Documentation

**STATUS: IN PROGRESS**

## Goal

Create polished examples covering every MCP capability. Achieve feature parity with FastMCP. Ship to dedalus_docs.

## Progress

### Phase 1: Example Structure ✅

Cleaned up legacy examples. New structure:

```
examples/
├── showcase/           # Hero examples (tested, working)
├── capabilities/       # MCP spec coverage
│   ├── tools/         ✅ typed, tags, context
│   ├── resources/     ✅ static, templates
│   ├── prompts/       ✅ basic prompts
│   ├── sampling/      ✅ server→client LLM
│   └── elicitation/   ✅ server→client input
├── patterns/          # Design patterns
│   ├── context_vs_script.py  ✅
│   ├── multi_server.py       ✅
│   └── testing.py            ✅
├── integrations/      
│   └── fastapi_migration.py  ✅
├── advanced/
│   └── llm_chain.py          ✅ (MCP server chaining!)
├── client/            # Client examples
└── auth/              # Auth flows
```

### Phase 2: FastMCP Feature Parity ✅

| FastMCP Feature | Dedalus MCP Equivalent | Status |
|-----------------|-------------------|--------|
| `@mcp.tool` decorator | `@tool` + `server.collect()` | ✅ Better |
| `@mcp.resource` | `@resource` + `server.collect()` | ✅ |
| `@mcp.prompt` | `@prompt` + `server.collect()` | ✅ |
| Tool tags | `@tool(tags={"a","b"})` | ✅ |
| Allow-lists | `server.tools.allow_tools()` | ✅ |
| Typed inputs | Native type hints + Pydantic | ✅ |
| Sampling | `server.request_sampling()` | ✅ |
| Elicitation | `server.request_elicitation()` | ✅ |
| Progress | `ctx.progress()` | ✅ |
| Logging | `ctx.info/debug/warning/error` | ✅ |
| Resource templates | `@resource_template` | ✅ |
| FastAPI integration | Migration example | ✅ |
| Multi-server | Native support | ✅ Better |
| Testing patterns | pytest examples | ✅ |

**Dedalus MCP advantages over FastMCP:**
- Decoupled registration (tools not bound at decoration time)
- Multi-server without re-decoration
- Script-style client API
- DPoP authentication (RFC 9449)
- MCP server chaining demo

### Phase 3: Documentation

- [x] `examples/README.md` with FastMCP comparison
- [ ] Ship to dedalus_docs `/docs/src/_content/dedalus_mcp/`
- [ ] Add tmux debugging guide
- [ ] Update navigation

### Phase 4: Testing

- [x] All examples compile
- [x] Showcase examples tested via `run_all.sh`
- [x] LLM chain example tested
- [ ] Full pytest suite for examples

## Files Changed

**New:**
- `examples/README.md` — Master README with FastMCP comparison
- `examples/capabilities/tools/01_typed_tools.py`
- `examples/capabilities/tools/02_tags_and_filtering.py`
- `examples/capabilities/tools/03_context_access.py`
- `examples/capabilities/resources/01_static_resources.py`
- `examples/capabilities/resources/02_resource_templates.py`
- `examples/capabilities/prompts/01_basic_prompts.py`
- `examples/capabilities/sampling/server.py`
- `examples/capabilities/sampling/client.py`
- `examples/capabilities/elicitation/server.py`
- `examples/capabilities/elicitation/client.py`
- `examples/patterns/testing.py`
- `examples/patterns/multi_server.py`
- `examples/advanced/llm_chain.py`

**Removed:**
- Legacy `examples/tools/`, `examples/resources/`, `examples/prompts/`
- `examples/dynamic_server.py`, `examples/cancellation.py`, etc.

## Next Steps

1. Ship examples to dedalus_docs
2. Add debugging guide
3. Consider CLI tool (`dedalus_mcp run server.py`)
