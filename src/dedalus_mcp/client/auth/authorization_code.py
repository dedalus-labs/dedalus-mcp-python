# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""OAuth 2.0 Authorization Code Grant (RFC 6749 Section 4.1).

AuthorizationCodeAuth is for browser-based flows where the user
authenticates via redirect.

TODO: Implement with Clerk integration for browser flows.
"""

from __future__ import annotations


class AuthorizationCodeAuth:
    """OAuth 2.0 Authorization Code Grant (RFC 6749 Section 4.1).

    Not yet implemented. Planned for Clerk integration.
    """

    def __init__(self) -> None:
        raise NotImplementedError(
            "AuthorizationCodeAuth is not yet implemented. "
            "Planned for Clerk integration."
        )
