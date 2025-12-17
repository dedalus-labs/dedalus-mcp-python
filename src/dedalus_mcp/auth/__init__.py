# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Dedalus MCP authentication primitives.

Usage:
    from dedalus_mcp.auth import Connection, SecretKeys, Binding, SecretValues

    # Define what secrets a connection needs
    github = Connection(
        'github',
        secrets=SecretKeys(token='GITHUB_TOKEN'),
        base_url='https://api.github.com',
    )

    # At runtime, bind actual secret values
    secrets = SecretValues(github, token='ghp_xxx')
"""

from .credentials import (
    _UNSET,
    ApiKeyCredentialEnvelope,
    Binding,
    Connection,
    Credential,
    CredentialEnvelope,
    Credentials,
    OAuth2CredentialEnvelope,
    ProviderMetadata,
    SecretKeys,
    SecretValues,
)


__all__ = [
    '_UNSET',
    'ApiKeyCredentialEnvelope',
    'Binding',
    'Connection',
    'Credential',
    'CredentialEnvelope',
    'Credentials',
    'OAuth2CredentialEnvelope',
    'ProviderMetadata',
    'SecretKeys',
    'SecretValues',
]
