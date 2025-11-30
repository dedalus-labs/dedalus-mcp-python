# Guidelines for Coding Agents

OpenMCP implements the Model Context Protocol. Spec-faithful, minimal surface.

## Quick Reference

| What | Where |
|------|-------|
| MCP spec | `internals/references/modelcontextprotocol/` |
| Reference SDK | `internals/references/python-sdk/` |
| Server core | `src/openmcp/server/core.py` |
| Versioning | `src/openmcp/versioning.py` |
| Types | `src/openmcp/types/` |
| Tests | `tests/` |

## Before You Code

**Scan wide before you write.** Search for logic that already does what you need. Search for logic that could help your implementation. Understand where your contribution fits contextually within this codebase. Don't write a single line until you understand these relationships.

1. Grep (or rg) the codebase for related functionality. It may already exist!
2. Find the spec section for what you're implementing
3. Look at similar existing code for patterns and conventions
4. Identify code that your implementation should integrate with

## Test-Driven Development

**Write tests first.** This project follows TDD. Don't implement features in a vacuum—define what "correct" looks like before you write production code.

**The workflow:**

1. **Create or update an execspec** — For any significant work, maintain a local `EXECSPEC-{topic}.md` in `docs/openmcp/`. This is your working document: what you're building, what invariants must hold, what's done, what's next.

2. **Write a failing test** — Before implementing, write a test that captures an invariant from your execspec. The test should fail because the feature doesn't exist yet.

3. **Make it pass** — Write the minimal code to make the test pass. No more.

4. **Refactor** — Clean up while tests are green.

5. **Repeat** — Each passing test is a small victory. Accumulate these toward the full vision.

**Example execspec structure:**

```markdown
# EXECSPEC: Elicitation Support

## Goal
Implement client-side elicitation per MCP 2025-06-18.

## Invariants
- [ ] `elicit()` raises if server doesn't advertise elicitation capability
- [ ] Timeout triggers `ElicitationTimeoutError`
- [ ] Response schema is validated against `ElicitationResult`

## Progress
- [x] Basic request/response flow
- [ ] Timeout handling
- [ ] Schema validation
```

**Why this matters:** Tests are executable documentation. When you write `test_elicit_raises_without_capability()`, you're stating a contract. Future changes that break this contract will fail loudly. The execspec keeps you honest—it's easy to lose sight of the goal mid-implementation.

See `docs/openmcp/EXECSPEC*.md` for examples of how we track larger features.

## Core Rules

**Fail loudly.** Never silently degrade. Unknown enum? Raise. Unsupported version? Raise. Invalid config? Raise.

```python
# Bad
def get_version(v: str) -> str:
    return VERSIONS.get(v, "2025-06-18")  # Silent fallback

# Good
def get_version(v: str) -> str:
    if v not in VERSIONS:
        raise UnsupportedProtocolVersionError(v)
    return VERSIONS[v]
```

Silent fallbacks create bugs that "work" until production. Explicit failures are debuggable.

**Cite the spec.** Link to the spec clause in docstrings or comments.

```python
async def list_tools(self) -> ListToolsResult:
    """List available tools.
    
    See: docs/mcp/spec/schema-reference/tools-list.md
    """
```

**Minimal dependencies.** This project respects developers' dependency budgets. Every dependency is a burden on downstream users—install weight, security surface, version conflicts. Don't add packages unless absolutely necessary.

Core deps: `mcp`, `pydantic`. Everything else is optional. Before adding a dependency:
- Can you implement it in <50 lines? Do that instead.
- Is it only needed for one feature? Make it an optional extra.
- Is it a dev/test dependency? Keep it out of the main install.

## Registration Pattern

Decorators attach metadata. `collect()` registers.

```python
from openmcp import MCPServer, tool

@tool(description="Add numbers")
def add(a: int, b: int) -> int:
    return a + b

server = MCPServer("math")
server.collect(add)
```

Same function can register to multiple servers. No global state.

## Versioning

OpenMCP is a **temporal inscription of the MCP spec**—it respects that the protocol evolves over time. Every feature has a version where it originated, and our code must reflect this.

**Before implementing any feature, ask:**
- Which MCP version introduced this feature?
- Does it exist in earlier versions? If so, where did it originate?
- Is this a version-specific change, or does it span multiple versions?

Protocol versions are tracked in `src/openmcp/versioning.py`. Check `docs/openmcp/version-matrix.md` to see what exists where.

**When adding version-specific behavior:**

```python
from openmcp.versioning import current_profile, FeatureId

profile = current_profile()
if profile.supports(FeatureId.PROGRESS_MESSAGE_FIELD):
    message = "Processing..."
else:
    message = None
```

The SDK uses `exclude_none=True`. Set unsupported fields to `None`.

**Adding a new feature:**

1. **Find the origin version** — Read the spec changelogs to determine when the feature was introduced
2. **Register it correctly** — Add to `FEATURE_REGISTRY` with the correct `added=` version
3. **Consider backwards compatibility** — If the feature builds on earlier concepts, ensure those are also tracked
4. **Test across versions** — Write tests that verify the feature is absent in earlier versions and present in later ones

**Adding a new MCP version:**

1. Read changelog at `internals/references/modelcontextprotocol/docs/specification/{version}/changelog.mdx`
2. Add `V_YYYY_MM_DD` constant
3. Add `FeatureId` entries with correct `added=` dates
4. Write migration function
5. Add tests in `tests/protocol_versions/{version}/`

**Why this matters:** Users negotiate protocol versions with servers. If OpenMCP claims to support `2024-11-05` but includes features from `2025-06-18`, we break interoperability. The versioning system is our contract with the spec.

## Testing

Tests validate spec guarantees. Run:

```bash
uv run pytest tests/ -q
```

Each test should focus on one protocol behavior. Name tests after what they verify.

## File Organization

- One concept per file
- Services in `src/openmcp/server/services/`
- Types re-exported from `src/openmcp/types/`
- Examples in `examples/`

## Transports

Two official transports: STDIO and Streamable HTTP. Default is Streamable HTTP.

```python
await server.serve()  # HTTP on :8000
await server.serve(transport="stdio")  # STDIO
```

## When In Doubt

1. Check the MCP spec
2. Look at existing implementations
3. Fail explicitly rather than guess
4. Keep it minimal
