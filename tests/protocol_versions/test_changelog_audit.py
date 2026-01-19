# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Audit versioning infrastructure against MCP spec changelogs.

This file verifies that our FeatureId enum and migrations capture all granular
changes documented in the official MCP changelogs. It serves as a cross-reference
between the spec and our implementation.

See more:
- https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/specification/{version}/changelog.mdx
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

import pytest

from dedalus_mcp.versioning import MIGRATIONS, FeatureId, ProtocolVersion, V_2025_03_26, V_2025_06_18, V_2025_11_25


# --- Typed changelog structures ------------------------------------------------


class ChangeType(Enum):
    """Type of change as documented in MCP changelogs."""

    FEATURE_ADDED = auto()
    FEATURE_REMOVED = auto()
    FIELD_ADDED = auto()
    FIELD_REMOVED = auto()
    NORMATIVE = auto()  # SHOULD→MUST, clarifications
    SEMANTIC_CHANGE = auto()  # Same schema, different interpretation


@dataclass(frozen=True)
class ChangelogEntry:
    """A single entry from an MCP changelog."""

    key: str
    kind: ChangeType
    feature_id: FeatureId | None  # None for normative-only changes
    pr: str | None = None


@dataclass(frozen=True)
class VersionChangelog:
    """All changelog entries for a specific protocol version."""

    version: ProtocolVersion
    entries: tuple[ChangelogEntry, ...]

    @property
    def trackable_entries(self) -> tuple[ChangelogEntry, ...]:
        """Entries that have FeatureId mappings (excludes normative-only)."""
        return tuple(e for e in self.entries if e.feature_id is not None)

    @property
    def expected_features(self) -> set[FeatureId]:
        """Set of FeatureIds that should be in the migration."""
        return {e.feature_id for e in self.trackable_entries if e.feature_id}


# --- Changelog data (extracted from MCP spec) ----------------------------------
# When a new MCP version is released, add a VersionChangelog here by reading
# the changelog at: internals/references/modelcontextprotocol/docs/specification/{version}/changelog.mdx


CHANGELOG_2025_03_26 = VersionChangelog(
    version=V_2025_03_26,
    entries=(
        ChangelogEntry("auth_oauth_framework", ChangeType.FEATURE_ADDED, FeatureId.AUTH_OAUTH, pr="#133"),
        ChangelogEntry(
            "transport_streamable_http", ChangeType.FEATURE_ADDED, FeatureId.TRANSPORT_STREAMABLE_HTTP, pr="#206"
        ),
        ChangelogEntry("jsonrpc_batching", ChangeType.FEATURE_ADDED, FeatureId.JSONRPC_BATCHING, pr="#228"),
        ChangelogEntry("tools_annotations", ChangeType.FIELD_ADDED, FeatureId.TOOLS_ANNOTATIONS, pr="#185"),
        ChangelogEntry("progress_message_field", ChangeType.FIELD_ADDED, FeatureId.PROGRESS_MESSAGE_FIELD),
        ChangelogEntry("content_audio", ChangeType.FEATURE_ADDED, FeatureId.CONTENT_AUDIO),
        ChangelogEntry("completion_capability_flag", ChangeType.FEATURE_ADDED, FeatureId.COMPLETION_CAPABILITY_FLAG),
    ),
)

CHANGELOG_2025_06_18 = VersionChangelog(
    version=V_2025_06_18,
    entries=(
        ChangelogEntry("jsonrpc_batching_removed", ChangeType.FEATURE_REMOVED, FeatureId.JSONRPC_BATCHING, pr="#416"),
        ChangelogEntry("tools_structured_output", ChangeType.FIELD_ADDED, FeatureId.TOOLS_STRUCTURED_OUTPUT, pr="#371"),
        ChangelogEntry("auth_resource_server", ChangeType.FEATURE_ADDED, FeatureId.AUTH_RESOURCE_SERVER, pr="#338"),
        ChangelogEntry(
            "auth_resource_indicators", ChangeType.FEATURE_ADDED, FeatureId.AUTH_RESOURCE_INDICATORS, pr="#734"
        ),
        ChangelogEntry("elicitation", ChangeType.FEATURE_ADDED, FeatureId.ELICITATION, pr="#382"),
        ChangelogEntry("tools_resource_links", ChangeType.FIELD_ADDED, FeatureId.TOOLS_RESOURCE_LINKS, pr="#603"),
        ChangelogEntry(
            "transport_protocol_version_header",
            ChangeType.FIELD_ADDED,
            FeatureId.TRANSPORT_PROTOCOL_VERSION_HEADER,
            pr="#548",
        ),
        ChangelogEntry("lifecycle_normative_tightening", ChangeType.NORMATIVE, None),
        ChangelogEntry("schema_meta_extended", ChangeType.FIELD_ADDED, FeatureId.SCHEMA_META_EXTENDED, pr="#710"),
        ChangelogEntry(
            "completion_context_field", ChangeType.FIELD_ADDED, FeatureId.COMPLETION_CONTEXT_FIELD, pr="#598"
        ),
        ChangelogEntry("schema_title_field", ChangeType.FIELD_ADDED, FeatureId.SCHEMA_TITLE_FIELD, pr="#663"),
    ),
)

CHANGELOG_2025_11_25 = VersionChangelog(
    version=V_2025_11_25,
    entries=(
        ChangelogEntry("auth_oidc_discovery", ChangeType.FEATURE_ADDED, FeatureId.AUTH_OIDC_DISCOVERY, pr="#797"),
        ChangelogEntry("icons_metadata", ChangeType.FIELD_ADDED, FeatureId.ICONS_METADATA, pr="SEP-973"),
        ChangelogEntry(
            "auth_incremental_scope", ChangeType.FEATURE_ADDED, FeatureId.AUTH_INCREMENTAL_SCOPE, pr="SEP-835"
        ),
        ChangelogEntry("tool_names_guidance", ChangeType.NORMATIVE, None, pr="SEP-986"),
        ChangelogEntry("elicitation_enum_standards", ChangeType.SEMANTIC_CHANGE, None, pr="SEP-1330"),
        ChangelogEntry("elicitation_url_mode", ChangeType.FEATURE_ADDED, FeatureId.ELICITATION_URL_MODE, pr="SEP-1036"),
        ChangelogEntry("sampling_tool_calling", ChangeType.FIELD_ADDED, FeatureId.SAMPLING_TOOL_CALLING, pr="SEP-1577"),
        ChangelogEntry(
            "auth_client_id_metadata", ChangeType.FEATURE_ADDED, FeatureId.AUTH_CLIENT_ID_METADATA, pr="SEP-991"
        ),
        ChangelogEntry("tasks_experimental", ChangeType.FEATURE_ADDED, FeatureId.TASKS_EXPERIMENTAL, pr="SEP-1686"),
        ChangelogEntry("stdio_stderr_clarification", ChangeType.NORMATIVE, None, pr="#670"),
        ChangelogEntry("implementation_description", ChangeType.FIELD_ADDED, FeatureId.IMPLEMENTATION_DESCRIPTION),
        ChangelogEntry("transport_origin_403", ChangeType.NORMATIVE, None, pr="#1439"),
        ChangelogEntry("tool_input_validation_errors", ChangeType.SEMANTIC_CHANGE, None, pr="SEP-1303"),
        ChangelogEntry("sse_polling_support", ChangeType.FEATURE_ADDED, FeatureId.SSE_POLLING, pr="SEP-1699"),
        ChangelogEntry("auth_protected_resource_metadata", ChangeType.SEMANTIC_CHANGE, None, pr="SEP-985"),
        ChangelogEntry(
            "elicitation_default_values", ChangeType.FIELD_ADDED, FeatureId.ELICITATION_DEFAULT_VALUES, pr="SEP-1034"
        ),
        ChangelogEntry("schema_json_2020_12", ChangeType.NORMATIVE, None, pr="SEP-1613"),
        ChangelogEntry("schema_request_payload_decoupling", ChangeType.SEMANTIC_CHANGE, None, pr="#1284"),
    ),
)

ALL_CHANGELOGS: tuple[VersionChangelog, ...] = (CHANGELOG_2025_03_26, CHANGELOG_2025_06_18, CHANGELOG_2025_11_25)


# --- Helpers -------------------------------------------------------------------


def get_migration_for(version: ProtocolVersion):
    """Get the migration for a specific version."""
    return next((m for m in MIGRATIONS if m.version == version), None)


# --- Tests ---------------------------------------------------------------------


class TestChangelogCoverage:
    """Verify migrations match MCP spec changelogs.

    This is the key invariant: every trackable changelog entry must have a
    corresponding SpecChange in the migration, and vice versa.
    """

    @pytest.mark.parametrize("changelog", ALL_CHANGELOGS, ids=lambda c: str(c.version))
    def test_migration_covers_all_features(self, changelog: VersionChangelog):
        """Migration SpecChanges must match changelog entries."""
        migration = get_migration_for(changelog.version)
        assert migration is not None, f"No migration for {changelog.version}"

        declared = {c.feature for c in migration.changes}
        expected = changelog.expected_features

        assert declared == expected, (
            f"Migration mismatch for {changelog.version}.\n"
            f"Missing from migration: {expected - declared}\n"
            f"Extra in migration: {declared - expected}"
        )


class TestChangelogIntegrity:
    """Structural invariants for changelog test data itself."""

    @pytest.mark.parametrize("changelog", ALL_CHANGELOGS, ids=lambda c: str(c.version))
    def test_no_duplicate_keys(self, changelog: VersionChangelog):
        """Each changelog entry should have a unique key."""
        keys = [e.key for e in changelog.entries]
        assert len(keys) == len(set(keys)), f"Duplicate keys in {changelog.version}"

    @pytest.mark.parametrize("changelog", ALL_CHANGELOGS, ids=lambda c: str(c.version))
    def test_trackable_entries_have_feature_ids(self, changelog: VersionChangelog):
        """Non-normative/semantic entries must have FeatureId mappings."""
        for entry in changelog.entries:
            is_untraceable = entry.kind in (ChangeType.NORMATIVE, ChangeType.SEMANTIC_CHANGE)
            if not is_untraceable:
                assert entry.feature_id is not None, f"{entry.key} should have a FeatureId"
