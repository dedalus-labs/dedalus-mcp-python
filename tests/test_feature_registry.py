# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Tests for versioning system invariants."""

from __future__ import annotations

from dedalus_mcp.versioning import (
    ALL_VERSIONS,
    MIGRATIONS,
    V_2024_11_05,
    V_2025_03_26,
    V_2025_06_18,
    V_2025_11_25,
    Availability,
    FeatureId,
    ProtocolProfile,
    capabilities_for,
    features_changed,
)


class TestMigrationsDrift:
    """Critical invariant: migrations' SpecChange lists match actual dataclass changes.

    This is THE test that prevents drift between declared changes and actual behavior.
    If you modify a capability dataclass field, you MUST update the corresponding
    migration's SpecChange list, or this test fails.
    """

    def test_migrations_match_declared_changes(self) -> None:
        caps_by_version = {v: capabilities_for(v) for v in ALL_VERSIONS}

        for prev, curr in zip(ALL_VERSIONS, ALL_VERSIONS[1:]):
            before = caps_by_version[prev]
            after = caps_by_version[curr]
            changed = features_changed(before, after)

            migration = next(m for m in MIGRATIONS if m.version == curr)
            declared = {c.feature for c in migration.changes}

            assert changed == declared, f"Mismatch at {curr}: changed={changed}, declared={declared}"


class TestMigrationsIntegrity:
    """Structural invariants for migrations."""

    def test_migrations_sorted(self) -> None:
        """Migrations must be in chronological order for correct application."""
        versions = [m.version for m in MIGRATIONS]
        assert versions == sorted(versions)

    def test_no_duplicate_features_within_migration(self) -> None:
        """Each migration should not declare the same feature twice."""
        for m in MIGRATIONS:
            features = [c.feature for c in m.changes]
            assert len(features) == len(set(features)), f"Duplicate feature in {m.version}"


class TestFeatureLifecycle:
    """Tests for features that have interesting lifecycles (add → remove)."""

    def test_batching_lifecycle(self) -> None:
        """JSON-RPC batching: UNAVAILABLE → AVAILABLE → REMOVED."""
        baseline = ProtocolProfile.for_version(V_2024_11_05)
        added = ProtocolProfile.for_version(V_2025_03_26)
        removed = ProtocolProfile.for_version(V_2025_06_18)
        latest = ProtocolProfile.for_version(V_2025_11_25)

        assert baseline.feature_state(FeatureId.JSONRPC_BATCHING) is Availability.UNAVAILABLE
        assert added.feature_state(FeatureId.JSONRPC_BATCHING) is Availability.AVAILABLE
        assert removed.feature_state(FeatureId.JSONRPC_BATCHING) is Availability.REMOVED
        assert latest.feature_state(FeatureId.JSONRPC_BATCHING) is Availability.REMOVED


class TestMigrationsCumulative:
    """Features from earlier versions remain available in later versions."""

    def test_earlier_features_persist(self) -> None:
        """Features added in 2025-03-26 should still be available in 2025-11-25."""
        latest = ProtocolProfile.for_version(V_2025_11_25)

        # 2025-03-26 additions
        assert latest.supports(FeatureId.PROGRESS_MESSAGE_FIELD)
        assert latest.supports(FeatureId.TOOLS_ANNOTATIONS)
        assert latest.supports(FeatureId.CONTENT_AUDIO)

        # 2025-06-18 additions
        assert latest.supports(FeatureId.ELICITATION)
        assert latest.supports(FeatureId.TOOLS_STRUCTURED_OUTPUT)
