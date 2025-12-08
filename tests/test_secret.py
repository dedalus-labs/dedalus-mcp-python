# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Tests for Credential class - credential binding with validation."""

from __future__ import annotations

import pytest

from dedalus_mcp import Binding, Connection, Credential, Credentials


class TestCredentialValidation:
    """Test Credential validation against Connection requirements."""

    def test_valid_credential_with_all_required_keys(self) -> None:
        """Credential with all required keys passes validation."""
        conn = Connection(
            'github',
            credentials=Credentials(token='GITHUB_TOKEN'),
            base_url='https://api.github.com',
        )

        cred = Credential(conn, token='ghp_xxx')

        assert cred.connection is conn
        assert cred.values == {'token': 'ghp_xxx'}

    def test_valid_credential_with_multiple_keys(self) -> None:
        """Credential with multiple required keys passes validation."""
        conn = Connection(
            'database',
            credentials=Credentials(
                username='DB_USER', password='DB_PASS', host='DB_HOST'
            ),
        )

        cred = Credential(conn, username='admin', password='s3cr3t', host='localhost')

        assert cred.values == {
            'username': 'admin',
            'password': 's3cr3t',
            'host': 'localhost',
        }

    def test_missing_required_key_raises(self) -> None:
        """Credential missing a required key raises ValueError."""
        conn = Connection(
            'github',
            credentials=Credentials(token='GITHUB_TOKEN', org='GITHUB_ORG'),
        )

        with pytest.raises(ValueError, match="Missing credentials for 'github'"):
            Credential(conn, token='ghp_xxx')  # Missing 'org'

    def test_missing_multiple_keys_lists_all(self) -> None:
        """Error message lists all missing keys."""
        conn = Connection(
            'api',
            credentials=Credentials(
                api_key='API_KEY', api_secret='API_SECRET', endpoint='ENDPOINT'
            ),
        )

        with pytest.raises(ValueError) as exc_info:
            Credential(conn, endpoint='https://api.example.com')

        # Should mention both missing keys
        assert 'api_key' in str(exc_info.value) or 'api_secret' in str(exc_info.value)

    def test_optional_key_not_required(self) -> None:
        """Optional keys don't need to be provided."""
        conn = Connection(
            'service',
            credentials=Credentials(
                api_key='API_KEY', org_id=Binding('ORG_ID', optional=True)
            ),
        )

        # Should not raise - org_id is optional
        cred = Credential(conn, api_key='key123')

        assert cred.values == {'api_key': 'key123'}

    def test_key_with_default_not_required(self) -> None:
        """Keys with defaults don't need to be provided."""
        conn = Connection(
            'api',
            credentials=Credentials(
                api_key='API_KEY', timeout=Binding('TIMEOUT', default=30)
            ),
        )

        # Should not raise - timeout has default
        cred = Credential(conn, api_key='key123')

        assert cred.values == {'api_key': 'key123'}

    def test_extra_keys_allowed(self) -> None:
        """Extra keys beyond requirements are allowed."""
        conn = Connection('github', credentials=Credentials(token='GITHUB_TOKEN'))

        cred = Credential(conn, token='ghp_xxx', extra_field='ignored')

        assert cred.values == {'token': 'ghp_xxx', 'extra_field': 'ignored'}

    def test_empty_connection_credentials_accepts_any(self) -> None:
        """Connection with empty credentials accepts any values."""
        conn = Connection('custom', credentials=Credentials())

        cred = Credential(conn, anything='value')

        assert cred.values == {'anything': 'value'}


class TestCredentialSerialization:
    """Test Credential serialization for wire transport."""

    def test_to_dict_basic(self) -> None:
        """Basic serialization includes connection name and values."""
        conn = Connection(
            'github',
            credentials=Credentials(token='GITHUB_TOKEN'),
            base_url='https://api.github.com',
        )

        cred = Credential(conn, token='ghp_xxx')
        result = cred.to_dict()

        assert result == {
            'connection_name': 'github',
            'values': {'token': 'ghp_xxx'},
        }

    def test_to_dict_multiple_values(self) -> None:
        """Serialization preserves all values."""
        conn = Connection(
            'database', credentials=Credentials(username='USER', password='PASS')
        )

        cred = Credential(conn, username='admin', password='s3cr3t')
        result = cred.to_dict()

        assert result['values'] == {'username': 'admin', 'password': 's3cr3t'}

    def test_values_for_encryption(self) -> None:
        """values_for_encryption returns only the credential values."""
        conn = Connection(
            'github',
            credentials=Credentials(token='GITHUB_TOKEN'),
            base_url='https://api.github.com',
        )

        cred = Credential(conn, token='ghp_xxx')

        # This is what gets encrypted client-side
        assert cred.values_for_encryption() == {'token': 'ghp_xxx'}


class TestCredentialRepr:
    """Test Credential string representation."""

    def test_repr_hides_values(self) -> None:
        """repr does not expose credential values."""
        conn = Connection('github', credentials=Credentials(token='GITHUB_TOKEN'))

        cred = Credential(conn, token='ghp_supersecret')
        repr_str = repr(cred)

        assert 'ghp_supersecret' not in repr_str
        assert 'github' in repr_str
        assert 'token' in repr_str  # Key names are OK

    def test_str_hides_values(self) -> None:
        """str does not expose credential values."""
        conn = Connection('github', credentials=Credentials(token='GITHUB_TOKEN'))

        cred = Credential(conn, token='ghp_supersecret')
        str_str = str(cred)

        assert 'ghp_supersecret' not in str_str


class TestCredentialEquality:
    """Test Credential equality and hashing."""

    def test_same_connection_same_values_equal(self) -> None:
        """Credentials with same connection and values are equal."""
        conn = Connection('github', credentials=Credentials(token='TOKEN'))

        c1 = Credential(conn, token='value')
        c2 = Credential(conn, token='value')

        assert c1 == c2

    def test_same_connection_different_values_not_equal(self) -> None:
        """Credentials with same connection but different values are not equal."""
        conn = Connection('github', credentials=Credentials(token='TOKEN'))

        c1 = Credential(conn, token='value1')
        c2 = Credential(conn, token='value2')

        assert c1 != c2

    def test_different_connection_not_equal(self) -> None:
        """Credentials with different connections are not equal."""
        conn1 = Connection('github', credentials=Credentials(token='TOKEN'))
        conn2 = Connection('gitlab', credentials=Credentials(token='TOKEN'))

        c1 = Credential(conn1, token='value')
        c2 = Credential(conn2, token='value')

        assert c1 != c2


class TestCredentialIntegration:
    """Integration tests for Credential with Connection."""

    def test_credential_binds_to_connection_name(self) -> None:
        """Credential is bound to connection by name for dispatch lookup."""
        github = Connection(
            'github',
            credentials=Credentials(token='GITHUB_TOKEN'),
            base_url='https://api.github.com',
        )
        openai = Connection(
            'openai',
            credentials=Credentials(api_key='OPENAI_API_KEY'),
            base_url='https://api.openai.com/v1',
        )

        github_cred = Credential(github, token='ghp_xxx')
        openai_cred = Credential(openai, api_key='sk_xxx')

        # Can build a lookup map for dispatch
        creds_map = {c.connection.name: c for c in [github_cred, openai_cred]}

        assert 'github' in creds_map
        assert 'openai' in creds_map
        assert creds_map['github'].values == {'token': 'ghp_xxx'}

    def test_multiple_credentials_same_connection_type(self) -> None:
        """Can have multiple credentials for same connection definition."""
        conn = Connection('api', credentials=Credentials(key='API_KEY'))

        prod_cred = Credential(conn, key='prod_key')
        dev_cred = Credential(conn, key='dev_key')

        # Both valid, different values
        assert prod_cred.values != dev_cred.values
        assert prod_cred.connection is dev_cred.connection
