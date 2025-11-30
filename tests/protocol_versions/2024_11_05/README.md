# MCP 2024-11-05 Specification Tests

This directory contains tests that verify OpenMCP's implementation against the **MCP 2024-11-05** specification.

## Specification Sources

- **Schema**: MCP 2024-11-05 JSON Schema
- **Prose Spec**: MCP 2024-11-05 specification documents

## Test Coverage

Each test file corresponds to a section of the 2024-11-05 specification:

- `test_initialization.py` - Lifecycle, version negotiation, capability negotiation
- `test_tools.py` - Tools capability (tools/list, tools/call, tools/list_changed)
- `test_resources.py` - Resources capability (resources/list, resources/read, subscribe/unsubscribe)
- `test_prompts.py` - Prompts capability (prompts/list, prompts/get)
- `test_utilities.py` - Ping, progress, cancellation, logging
- `test_sampling.py` - Client sampling capability (sampling/createMessage)

## Testing Approach

Tests in this directory validate that OpenMCP correctly implements the 2024-11-05 spec by:

1. **Structure Validation**: Ensuring messages match the JSON schema.
2. **Behavior Validation**: Verifying MUST/SHOULD/MAY requirements from prose specs.
3. **Error Handling**: Confirming proper error responses.
4. **Capability Negotiation**: Testing version-specific feature flags.

## Running Tests

```bash
# Run all 2024-11-05 tests
uv run pytest tests/protocol_versions/2024_11_05/

# Run specific capability tests
uv run pytest tests/protocol_versions/2024_11_05/test_tools.py
```
