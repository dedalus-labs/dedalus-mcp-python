# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Tests for serialization protocol compatibility between dedalus_mcp and SDK.

These tests verify that Connection and Credential objects serialize to JSON-compatible
formats that can be consumed by any SDK implementing the protocol, including:
- The Stainless-generated dedalus-sdk-python
- Third-party libraries implementing the same wire format
"""

from __future__ import annotations

import json
from typing import Any, Protocol, runtime_checkable

import pytest

from dedalus_mcp import Binding, Connection, Credential, Credentials


# --- Protocol definitions (what the SDK expects) ---


@runtime_checkable
class ConnectionProtocol(Protocol):
    """Protocol for Connection-like objects."""

    @property
    def name(self) -> str: ...

    @property
    def base_url(self) -> str | None: ...

    @property
    def timeout_ms(self) -> int: ...

    def to_dict(self) -> dict[str, Any]: ...


@runtime_checkable
class CredentialProtocol(Protocol):
    """Protocol for Credential-like objects."""

    @property
    def connection(self) -> ConnectionProtocol: ...

    @property
    def values(self) -> dict[str, Any]: ...

    def to_dict(self) -> dict[str, Any]: ...

    def values_for_encryption(self) -> dict[str, Any]: ...


class TestConnectionProtocol:
    """Test that Connection satisfies the protocol."""

    def test_connection_satisfies_protocol(self) -> None:
        """Connection class implements ConnectionProtocol."""
        conn = Connection(
            'github',
            credentials=Credentials(token='GITHUB_TOKEN'),
            base_url='https://api.github.com',
        )
        assert isinstance(conn, ConnectionProtocol)

    def test_connection_to_dict_is_json_serializable(self) -> None:
        """Connection.to_dict() produces JSON-serializable output."""
        conn = Connection(
            'github',
            credentials=Credentials(
                token='GITHUB_TOKEN', org=Binding('GITHUB_ORG', optional=True)
            ),
            base_url='https://api.github.com',
            timeout_ms=60000,
        )

        data = conn.to_dict()

        # Must be JSON-serializable
        json_str = json.dumps(data)
        parsed = json.loads(json_str)

        assert parsed['name'] == 'github'
        assert parsed['base_url'] == 'https://api.github.com'
        assert parsed['timeout_ms'] == 60000
        assert 'credentials' in parsed
        assert parsed['credentials']['token'] == 'GITHUB_TOKEN'

    def test_connection_to_dict_omits_defaults(self) -> None:
        """to_dict() omits default values for compact wire format."""
        conn = Connection('github', credentials=Credentials(token='TOKEN'))

        data = conn.to_dict()

        assert 'base_url' not in data  # None by default
        assert 'timeout_ms' not in data  # 30000 is default


class TestCredentialProtocol:
    """Test that Credential satisfies the protocol."""

    def test_credential_satisfies_protocol(self) -> None:
        """Credential class implements CredentialProtocol."""
        conn = Connection('github', credentials=Credentials(token='TOKEN'))
        cred = Credential(conn, token='ghp_xxx')

        assert isinstance(cred, CredentialProtocol)

    def test_credential_to_dict_is_json_serializable(self) -> None:
        """Credential.to_dict() produces JSON-serializable output."""
        conn = Connection('github', credentials=Credentials(token='TOKEN'))
        cred = Credential(conn, token='ghp_xxx')

        data = cred.to_dict()

        json_str = json.dumps(data)
        parsed = json.loads(json_str)

        assert parsed['connection_name'] == 'github'
        assert parsed['values'] == {'token': 'ghp_xxx'}

    def test_values_for_encryption_is_json_serializable(self) -> None:
        """values_for_encryption() produces JSON-serializable output."""
        conn = Connection('api', credentials=Credentials(key='KEY', secret='SECRET'))
        cred = Credential(conn, key='k123', secret='s456')

        data = cred.values_for_encryption()

        json_str = json.dumps(data)
        parsed = json.loads(json_str)

        assert parsed == {'key': 'k123', 'secret': 's456'}


class TestWireFormatRoundTrip:
    """Test wire format round-trip compatibility."""

    def test_connection_round_trip(self) -> None:
        """Connection survives JSON round-trip."""
        conn = Connection(
            'openai',
            credentials=Credentials(
                api_key='OPENAI_API_KEY',
                org_id=Binding('OPENAI_ORG', default='default_org'),
            ),
            base_url='https://api.openai.com/v1',
            timeout_ms=120000,
        )

        wire = json.dumps(conn.to_dict())
        parsed = json.loads(wire)

        # Verify all fields preserved
        assert parsed['name'] == 'openai'
        assert parsed['base_url'] == 'https://api.openai.com/v1'
        assert parsed['timeout_ms'] == 120000
        assert parsed['credentials']['api_key'] == 'OPENAI_API_KEY'
        assert parsed['credentials']['org_id']['default'] == 'default_org'

    def test_multiple_connections_serialize(self) -> None:
        """Multiple connections serialize to array."""
        github = Connection('github', credentials=Credentials(token='TOKEN'))
        openai = Connection('openai', credentials=Credentials(api_key='KEY'))

        wire = json.dumps([c.to_dict() for c in [github, openai]])
        parsed = json.loads(wire)

        assert len(parsed) == 2
        assert parsed[0]['name'] == 'github'
        assert parsed[1]['name'] == 'openai'

    def test_credentials_list_serialize(self) -> None:
        """Credentials list serializes for SDK consumption."""
        github = Connection('github', credentials=Credentials(token='TOKEN'))
        openai = Connection('openai', credentials=Credentials(api_key='KEY'))

        creds = [
            Credential(github, token='ghp_xxx'),
            Credential(openai, api_key='sk_xxx'),
        ]

        wire = json.dumps([c.to_dict() for c in creds])
        parsed = json.loads(wire)

        assert len(parsed) == 2
        assert parsed[0]['connection_name'] == 'github'
        assert parsed[0]['values'] == {'token': 'ghp_xxx'}
        assert parsed[1]['connection_name'] == 'openai'
        assert parsed[1]['values'] == {'api_key': 'sk_xxx'}


class TestDuckTypingCompatibility:
    """Test that duck-typed objects work with serialization helpers."""

    def test_custom_connection_like_object(self) -> None:
        """Custom objects with to_dict() work."""

        class CustomConnection:
            def __init__(self, name: str, base_url: str) -> None:
                self._name = name
                self._base_url = base_url

            @property
            def name(self) -> str:
                return self._name

            @property
            def base_url(self) -> str | None:
                return self._base_url

            @property
            def timeout_ms(self) -> int:
                return 30000

            @property
            def credentials(self) -> Any:
                return None

            def to_dict(self) -> dict[str, Any]:
                return {'name': self._name, 'base_url': self._base_url}

        custom = CustomConnection('custom', 'https://custom.api.com')

        # Satisfies protocol
        assert isinstance(custom, ConnectionProtocol)

        # Serializes
        wire = json.dumps(custom.to_dict())
        parsed = json.loads(wire)
        assert parsed['name'] == 'custom'

    def test_custom_credential_like_object(self) -> None:
        """Custom Credential-like objects work."""
        conn = Connection('github', credentials=Credentials(token='TOKEN'))

        class CustomCredential:
            def __init__(self, connection: Any, **values: Any) -> None:
                self._connection = connection
                self._values = values

            @property
            def connection(self) -> Any:
                return self._connection

            @property
            def values(self) -> dict[str, Any]:
                return dict(self._values)

            def to_dict(self) -> dict[str, Any]:
                return {
                    'connection_name': self._connection.name,
                    'values': self._values,
                }

            def values_for_encryption(self) -> dict[str, Any]:
                return dict(self._values)

        custom = CustomCredential(conn, token='xxx')

        # Satisfies protocol
        assert isinstance(custom, CredentialProtocol)

        # Serializes
        wire = json.dumps(custom.to_dict())
        parsed = json.loads(wire)
        assert parsed['connection_name'] == 'github'


class TestSDKIntegrationFormat:
    """Test the exact format expected by the SDK."""

    def test_connection_provisioning_payload(self) -> None:
        """Connection produces payload format for POST /connections."""
        conn = Connection(
            'github',
            credentials=Credentials(token='GITHUB_TOKEN'),
            base_url='https://api.github.com',
            timeout_ms=30000,
        )
        cred = Credential(conn, token='ghp_actual_secret')

        # This is what SDK sends to AS
        payload = {
            'name': conn.name,
            'base_url': conn.base_url,
            'timeout_ms': conn.timeout_ms,
            # encrypted_credentials would be RSA-encrypted version of:
            # json.dumps(cred.values_for_encryption())
        }

        assert payload['name'] == 'github'
        assert payload['base_url'] == 'https://api.github.com'
        assert payload['timeout_ms'] == 30000

        # Plaintext for encryption
        plaintext = json.dumps(cred.values_for_encryption())
        assert plaintext == '{"token": "ghp_actual_secret"}'

    def test_multiple_connections_provisioning(self) -> None:
        """Multiple connections/credentials produce correct provisioning batch."""
        github = Connection(
            'github',
            credentials=Credentials(token='TOKEN'),
            base_url='https://api.github.com',
        )
        openai = Connection(
            'openai',
            credentials=Credentials(api_key='KEY'),
            base_url='https://api.openai.com/v1',
        )

        github_cred = Credential(github, token='ghp_xxx')
        openai_cred = Credential(openai, api_key='sk_xxx')

        # SDK would iterate and provision each
        provisions = []
        for conn, cred in [(github, github_cred), (openai, openai_cred)]:
            provisions.append(
                {
                    'name': conn.name,
                    'base_url': conn.base_url,
                    'timeout_ms': conn.timeout_ms,
                    'plaintext_for_encryption': cred.values_for_encryption(),
                }
            )

        assert len(provisions) == 2
        assert provisions[0]['name'] == 'github'
        assert provisions[0]['plaintext_for_encryption'] == {'token': 'ghp_xxx'}
        assert provisions[1]['name'] == 'openai'
        assert provisions[1]['plaintext_for_encryption'] == {'api_key': 'sk_xxx'}
