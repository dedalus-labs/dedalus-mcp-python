# MCP Version Matrix

This document tracks MCP protocol features across versions with spec citations.

**Source of truth**: `internals/references/modelcontextprotocol/docs/specification/`

## Version Timeline

| Version | Status | Release Notes |
|---------|--------|---------------|
| 2024-11-05 | Final | First public release |
| 2025-03-26 | Final | OAuth, Streamable HTTP, tool annotations |
| 2025-06-18 | Current | Elicitation, structured output, security |
| 2025-11-25 | Draft | Tasks, icons, enhanced OAuth |
| draft | Draft | Unreleased changes |

## Feature Matrix

### Core Protocol

| Feature | 2024-11-05 | 2025-03-26 | 2025-06-18 | 2025-11-25 | Notes |
|---------|------------|------------|------------|------------|-------|
| Lifecycle (initialize/initialized) | ✓ | ✓ | ✓ | ✓ | |
| STDIO transport | ✓ | ✓ | ✓ | ✓ | |
| HTTP+SSE transport | ✓ | — | — | — | Replaced by Streamable HTTP |
| Streamable HTTP transport | — | ✓ | ✓ | ✓ | PR #206 |
| JSON-RPC batching | — | ✓ | — | — | Added then removed (PR #416) |
| MCP-Protocol-Version header | — | — | ✓ | ✓ | Required for HTTP (PR #548) |

### Server Capabilities

| Feature | 2024-11-05 | 2025-03-26 | 2025-06-18 | 2025-11-25 | Notes |
|---------|------------|------------|------------|------------|-------|
| Tools | ✓ | ✓ | ✓ | ✓ | |
| Tool annotations | — | ✓ | ✓ | ✓ | readOnly, destructive (PR #185) |
| Structured tool output | — | — | ✓ | ✓ | PR #371 |
| Resource links in results | — | — | ✓ | ✓ | PR #603 |
| Tool icons | — | — | — | ✓ | SEP-973 |
| Resources | ✓ | ✓ | ✓ | ✓ | |
| Resource icons | — | — | — | ✓ | SEP-973 |
| Prompts | ✓ | ✓ | ✓ | ✓ | |
| Prompt icons | — | — | — | ✓ | SEP-973 |
| Completion | ✓ | ✓ | ✓ | ✓ | |
| Completion context field | — | — | ✓ | ✓ | PR #598 |
| Completions capability flag | — | ✓ | ✓ | ✓ | Explicit capability |
| Logging | ✓ | ✓ | ✓ | ✓ | |
| Pagination | ✓ | ✓ | ✓ | ✓ | |

### Client Capabilities

| Feature | 2024-11-05 | 2025-03-26 | 2025-06-18 | 2025-11-25 | Notes |
|---------|------------|------------|------------|------------|-------|
| Roots | ✓ | ✓ | ✓ | ✓ | |
| Sampling | ✓ | ✓ | ✓ | ✓ | |
| Sampling with tools | — | — | — | ✓ | SEP-1577 |
| Elicitation | — | — | ✓ | ✓ | PR #382 |
| URL mode elicitation | — | — | — | ✓ | SEP-1036 |

### Utilities

| Feature | 2024-11-05 | 2025-03-26 | 2025-06-18 | 2025-11-25 | Notes |
|---------|------------|------------|------------|------------|-------|
| Ping | ✓ | ✓ | ✓ | ✓ | |
| Progress | ✓ | ✓ | ✓ | ✓ | |
| Progress message field | — | ✓ | ✓ | ✓ | |
| Cancellation | ✓ | ✓ | ✓ | ✓ | |
| Tasks | — | — | — | ✓ | Experimental (SEP-1686) |

### Content Types

| Feature | 2024-11-05 | 2025-03-26 | 2025-06-18 | 2025-11-25 | Notes |
|---------|------------|------------|------------|------------|-------|
| Text content | ✓ | ✓ | ✓ | ✓ | |
| Image content | ✓ | ✓ | ✓ | ✓ | |
| Audio content | — | ✓ | ✓ | ✓ | |

### Authorization

| Feature | 2024-11-05 | 2025-03-26 | 2025-06-18 | 2025-11-25 | Notes |
|---------|------------|------------|------------|------------|-------|
| OAuth 2.1 framework | — | ✓ | ✓ | ✓ | PR #133 |
| Resource Server classification | — | — | ✓ | ✓ | PR #338 |
| Resource Indicators (RFC 8707) | — | — | ✓ | ✓ | PR #734 |
| OpenID Connect discovery | — | — | — | ✓ | PR #797 |
| Incremental scope consent | — | — | — | ✓ | SEP-835 |
| OAuth Client ID Metadata | — | — | — | ✓ | SEP-991 |

### Schema Additions

| Feature | 2024-11-05 | 2025-03-26 | 2025-06-18 | 2025-11-25 | Notes |
|---------|------------|------------|------------|------------|-------|
| `title` field (display names) | — | — | ✓ | ✓ | PR #663 |
| `_meta` field extended | — | — | ✓ | ✓ | PR #710 |
| `description` in Implementation | — | — | — | ✓ | |

## Non-Code Spec Items

These spec sections don't correspond to Dedalus MCP code:

| Section | Version | Description |
|---------|---------|-------------|
| Governance | 2025-11-25 | SEP-932: Governance structure |
| Communication | 2025-11-25 | SEP-994: Community guidelines |
| Working Groups | 2025-11-25 | SEP-1302: WG/IG structure |
| SDK Tiering | 2025-11-25 | SEP-1730: SDK requirements |
| Security Best Practices | 2025-06-18 | Guidance document |

## Dedalus MCP Support Status

| Version | Support | Notes |
|---------|---------|-------|
| 2024-11-05 | ✓ Full | Schema validated |
| 2025-03-26 | ✓ Full | Schema validated |
| 2025-06-18 | ✓ Full | Schema validated, current target |
| 2025-11-25 | ✗ Not yet | Tasks, icons, enhanced elicitation pending |

## Updating This Document

When a new MCP version is released:

1. Read `internals/references/modelcontextprotocol/docs/specification/{version}/changelog.mdx`
2. Update the feature matrix above
3. Add new `ProtocolDefinition` in `src/dedalus_mcp/versioning.py`
4. Copy schema to `tests/protocol_versions/{version}/schema.json`
5. Add version-specific tests

## References

- MCP Spec Repository: `internals/references/modelcontextprotocol/`
- Schemas: `internals/references/modelcontextprotocol/schema/{version}/schema.json`
- Changelogs: `internals/references/modelcontextprotocol/docs/specification/{version}/changelog.mdx`
