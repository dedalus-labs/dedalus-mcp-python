# Versioning

Dedalus MCP is a **temporal inscription of the MCP spec**—it respects that the protocol evolves over time. Every feature has a version where it originated, and our code must reflect this.

This module tracks MCP protocol versions at a granular level, allowing code to query whether specific features exist in a given protocol revision.

## Quick Start

```python
from dedalus_mcp.versioning import ProtocolProfile, FeatureId

# Get capabilities for a specific version
profile = ProtocolProfile.for_version("2025-06-18")

# Check feature support
if profile.supports(FeatureId.PROGRESS_MESSAGE_FIELD):
    message = "Processing step 3 of 10"
else:
    message = None

# Direct capability access
profile.caps.progress.message  # FieldStatus.OPTIONAL
profile.caps.jsonrpc.batching  # BatchingState.REMOVED
```

## Why Typed Capabilities?

MCP evolves incrementally. A "feature" in version 1.0 might gain new fields in version 1.1. Tracking just "feature present/absent" is insufficient. Dedalus MCP tracks every incremental change so code can behave correctly for each protocol revision.

Example: `ProgressNotification` existed in 2024-11-05, but the optional `message` field was added in 2025-03-26. A server negotiating 2024-11-05 should NOT send `message` (older clients won't understand it).

## API Reference

### `ProtocolProfile.for_version(version: str) -> ProtocolProfile`

Get a profile for a specific protocol version:

```python
profile = ProtocolProfile.for_version("2025-03-26")
profile.version  # ProtocolVersion(date=datetime.date(2025, 3, 26))
profile.caps     # ProtocolCaps with all fields populated
```

Raises `UnsupportedProtocolVersionError` for unknown versions.

### `profile.supports(feature: FeatureId) -> bool`

Check if a feature is available (either AVAILABLE or DEPRECATED):

```python
# True - message field exists in 2025-03-26
profile = ProtocolProfile.for_version("2025-03-26")
profile.supports(FeatureId.PROGRESS_MESSAGE_FIELD)

# False - message field didn't exist yet
profile = ProtocolProfile.for_version("2024-11-05")
profile.supports(FeatureId.PROGRESS_MESSAGE_FIELD)
```

### `profile.feature_state(feature: FeatureId) -> Availability`

Get the detailed availability state:

```python
from dedalus_mcp.versioning import Availability

state = profile.feature_state(FeatureId.JSONRPC_BATCHING)
# Availability.UNSUPPORTED / AVAILABLE / DEPRECATED / REMOVED
```

### Direct Capability Access

For more granular control, access capability dataclasses directly:

```python
profile.caps.progress.message    # FieldStatus.ABSENT / OPTIONAL / REQUIRED
profile.caps.jsonrpc.batching    # BatchingState.UNSUPPORTED / SUPPORTED / REMOVED
profile.caps.elicitation.enabled # True / False
```

## Runtime Integration

The MCP SDK handles serialization with `exclude_none=True`, so the pattern for version-sensitive code is straightforward:

```python
profile = current_profile()  # from session context

# For optional fields added in later versions:
message = "Processing..." if profile.supports(FeatureId.PROGRESS_MESSAGE_FIELD) else None
session.send_progress_notification(token, progress, total, message=message)
# SDK omits `message` if None

# For whole capabilities:
if profile.supports(FeatureId.ELICITATION):
    result = await session.elicit_confirmation(...)
```

No SDK patching required. Check the profile, conditionally construct, let the SDK serialize.

## Supported Versions

| Version | Status | Key Additions |
|---------|--------|---------------|
| 2024-11-05 | Supported | First public release (baseline) |
| 2025-03-26 | Supported | OAuth, Streamable HTTP, progress message, JSON-RPC batching |
| 2025-06-18 | Supported | Elicitation, structured output, batching removed |

## Zero Fallback Policy

Dedalus MCP never silently falls back to a default version. If code requests an unsupported version, it raises `UnsupportedProtocolVersionError`:

```python
# Raises UnsupportedProtocolVersionError
ProtocolProfile.for_version("2020-01-01")
```

This prevents subtle bugs where code assumes one version's behavior but unknowingly receives another.

## Adding Support for a New Version

See the [Protocol Version Tests README](../../tests/protocol_versions/README.md) and [CONTRIBUTING.md](../../CONTRIBUTING.md) for the maintainer workflow.

## Spec References

- Lifecycle: `docs/mcp/core/lifecycle/lifecycle-phases.md`
- Initialize: `docs/mcp/spec/schema-reference/initialize.md`
- Version negotiation: `docs/mcp/capabilities/versioning`
