# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Core versioning tests."""

from __future__ import annotations

import pytest

from openmcp.versioning import (
    ALL_VERSIONS,
    LATEST_VERSION,
    SUPPORTED_VERSIONS,
    UnsupportedProtocolVersionError,
    ProtocolVersion,
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
