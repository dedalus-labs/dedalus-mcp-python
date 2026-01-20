# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Core versioning tests."""

from __future__ import annotations

import pytest

from dedalus_mcp.versioning import (
    ALL_VERSIONS,
    LATEST_VERSION,
    SUPPORTED_VERSIONS,
    FeatureId,
    ProtocolProfile,
    ProtocolVersion,
    UnsupportedProtocolVersionError,
    V_2025_11_25,
    capabilities_for,
)


class TestCapabilitiesFor:
    """capabilities_for() tests."""

    def test_all_supported_versions(self) -> None:
        """capabilities_for returns valid ProtocolCaps for all supported versions."""
        for v in ALL_VERSIONS:
            caps = capabilities_for(v)
            assert caps.version == v

    def test_cached(self) -> None:
        """capabilities_for results are cached (same object on repeated calls)."""
        caps1 = capabilities_for(LATEST_VERSION)
        caps2 = capabilities_for(LATEST_VERSION)
        assert caps1 is caps2

    def test_unsupported_version_raises(self) -> None:
        unknown = ProtocolVersion.parse("2020-01-01")
        with pytest.raises(UnsupportedProtocolVersionError) as exc_info:
            capabilities_for(unknown)
        assert exc_info.value.version == unknown
        assert exc_info.value.supported == SUPPORTED_VERSIONS


class TestProtocolProfile:
    """ProtocolProfile tests."""

    def test_parse_valid_version(self) -> None:
        """parse() creates profile from version string."""
        profile = ProtocolProfile.parse("2025-11-25")
        assert profile.version == V_2025_11_25

    def test_parse_invalid_format(self) -> None:
        """parse() returns None for malformed version strings."""
        assert ProtocolProfile.parse("not-a-date") is None
        assert ProtocolProfile.parse("") is None
        assert ProtocolProfile.parse("2025/11/25") is None

    def test_parse_unsupported_version(self) -> None:
        """parse() returns None for unsupported versions."""
        assert ProtocolProfile.parse("2020-01-01") is None

    def test_supports_feature(self) -> None:
        """supports() checks feature availability for the profile's version."""
        profile = ProtocolProfile.parse("2025-11-25")
        assert profile is not None
        assert profile.supports(FeatureId.AUTH_INCREMENTAL_SCOPE)

        old_profile = ProtocolProfile.parse("2025-06-18")
        assert old_profile is not None
        assert not old_profile.supports(FeatureId.AUTH_INCREMENTAL_SCOPE)
