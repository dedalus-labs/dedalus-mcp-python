# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Wire format types for credential envelopes."""

from __future__ import annotations

from typing import Literal, TypedDict


class ProviderMetadata(TypedDict, total=False):
    """Optional metadata about the credential provider.

    Attributes:
        base_url: Override URL for the provider (e.g., enterprise GitHub).
    """

    base_url: str | None


class ApiKeyCredentialEnvelope(TypedDict):
    """API key credential envelope for enclave decryption.

    Encrypted client-side; the enclave parses this to build the authentication
    header for downstream HTTP requests.

    Attributes:
        type: Discriminator, always ``"api_key"``.
        api_key: The actual API key value.
        header_name: HTTP header name (e.g., ``"Authorization"``).
        header_template: Format string for header value (e.g., ``"Bearer {api_key}"``).
        provider_metadata: Optional provider-specific metadata.
    """

    type: Literal["api_key"]
    api_key: str
    header_name: str
    header_template: str
    provider_metadata: ProviderMetadata | None


class OAuth2CredentialEnvelope(TypedDict):
    """OAuth2 credential envelope for enclave decryption.

    Attributes:
        type: Discriminator, always ``"oauth2"``.
        access_token: The OAuth2 access token.
        token_type: Token type (e.g., ``"Bearer"``).
        provider_metadata: Optional provider-specific metadata.
    """

    type: Literal["oauth2"]
    access_token: str
    token_type: str
    provider_metadata: ProviderMetadata | None


CredentialEnvelope = ApiKeyCredentialEnvelope | OAuth2CredentialEnvelope
"""Union type for all credential envelope formats."""

__all__ = ["ApiKeyCredentialEnvelope", "CredentialEnvelope", "OAuth2CredentialEnvelope", "ProviderMetadata"]
