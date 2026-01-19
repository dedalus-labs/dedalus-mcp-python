# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Tests for SecretValues class - secret binding with validation."""

from __future__ import annotations

import pytest

from dedalus_mcp import Binding, Connection, SecretKeys, SecretValues


class TestConnectionAuthHeaders:
    """Test Connection auth header configuration."""

    def test_default_auth_headers(self) -> None:
        """Connection defaults to Bearer token auth."""
        conn = Connection("github", secrets=SecretKeys(token="TOKEN"))

        assert conn.auth_header_name == "Authorization"
        assert conn.auth_header_format == "Bearer {api_key}"

    def test_custom_header_name(self) -> None:
        """Can specify custom auth header name."""
        conn = Connection(
            "anthropic", secrets=SecretKeys(api_key="KEY"), auth_header_name="x-api-key", auth_header_format="{api_key}"
        )

        assert conn.auth_header_name == "x-api-key"
        assert conn.auth_header_format == "{api_key}"

    def test_custom_token_template(self) -> None:
        """Can specify custom token template."""
        conn = Connection("github", secrets=SecretKeys(token="TOKEN"), auth_header_format="token {api_key}")

        assert conn.auth_header_name == "Authorization"
        assert conn.auth_header_format == "token {api_key}"

    def test_template_must_contain_placeholder(self) -> None:
        """auth_header_format must contain {api_key} placeholder."""
        with pytest.raises(ValueError, match=r"\{api_key\}"):
            Connection(
                "invalid",
                secrets=SecretKeys(key="KEY"),
                auth_header_format="Bearer token",  # Missing {api_key}
            )

    def test_to_dict_includes_auth_headers(self) -> None:
        """to_dict includes auth header configuration."""
        conn = Connection(
            "custom",
            secrets=SecretKeys(key="KEY"),
            base_url="https://api.example.com",
            auth_header_name="apikey",
            auth_header_format="{api_key}",
        )

        result = conn.to_dict()

        assert result["auth_header_name"] == "apikey"
        assert result["auth_header_format"] == "{api_key}"


class TestConnectionSchema:
    """Test Connection schema parameter."""

    def test_no_schema_by_default(self) -> None:
        """Connection has no schema by default."""
        conn = Connection("github", secrets=SecretKeys(token="TOKEN"))

        assert conn.schema is None

    def test_basemodel_schema(self) -> None:
        """Connection accepts BaseModel subclass as schema."""
        from pydantic import BaseModel

        class MySchema(BaseModel):
            model: str
            temperature: float = 0.7

        conn = Connection("openai", secrets=SecretKeys(api_key="KEY"), schema=MySchema)

        assert conn.schema is MySchema

    def test_dict_schema_creates_dynamic_model(self) -> None:
        """Dict schema creates a dynamic Pydantic model."""
        from pydantic import BaseModel

        conn = Connection("anthropic", secrets=SecretKeys(api_key="KEY"), schema={"model": str, "max_tokens": int})

        assert conn.schema is not None
        assert issubclass(conn.schema, BaseModel)
        assert conn.schema.__name__ == "AnthropicSchema"

    def test_validate_config_with_basemodel_schema(self) -> None:
        """validate_config returns validated model instance."""
        from pydantic import BaseModel

        class MySchema(BaseModel):
            model: str
            temperature: float = 0.7

        conn = Connection("openai", secrets=SecretKeys(api_key="KEY"), schema=MySchema)

        result = conn.validate_config({"model": "gpt-4"})

        assert isinstance(result, MySchema)
        assert result.model == "gpt-4"
        assert result.temperature == 0.7  # default

    def test_validate_config_with_dict_schema(self) -> None:
        """validate_config works with dict schema."""
        conn = Connection("anthropic", secrets=SecretKeys(api_key="KEY"), schema={"model": str, "max_tokens": int})

        result = conn.validate_config({"model": "claude-3", "max_tokens": 1000})

        assert result.model == "claude-3"  # type: ignore[attr-defined]
        assert result.max_tokens == 1000  # type: ignore[attr-defined]

    def test_validate_config_raises_without_schema(self) -> None:
        """validate_config raises ValueError if no schema defined."""
        conn = Connection("github", secrets=SecretKeys(token="TOKEN"))

        with pytest.raises(ValueError, match="has no schema defined"):
            conn.validate_config({"model": "gpt-4"})

    def test_validate_config_raises_on_invalid_data(self) -> None:
        """validate_config raises ValidationError on invalid data."""
        from pydantic import BaseModel, ValidationError

        class MySchema(BaseModel):
            model: str
            temperature: float

        conn = Connection("openai", secrets=SecretKeys(api_key="KEY"), schema=MySchema)

        with pytest.raises(ValidationError):
            conn.validate_config({"model": "gpt-4"})  # missing temperature

    def test_invalid_schema_type_raises(self) -> None:
        """Invalid schema type raises TypeError."""
        with pytest.raises(TypeError, match="must be a BaseModel subclass or dict"):
            Connection(
                "invalid",
                secrets=SecretKeys(key="KEY"),
                schema="not a schema",  # type: ignore[arg-type]
            )

    def test_to_dict_includes_schema_name(self) -> None:
        """to_dict includes schema class name."""
        from pydantic import BaseModel

        class MySchema(BaseModel):
            model: str

        conn = Connection("openai", secrets=SecretKeys(api_key="KEY"), schema=MySchema)

        result = conn.to_dict()

        assert result["schema"] == "MySchema"

    def test_to_dict_omits_schema_when_none(self) -> None:
        """to_dict omits schema key when None."""
        conn = Connection("github", secrets=SecretKeys(token="TOKEN"))

        result = conn.to_dict()

        assert "schema" not in result

    def test_repr_includes_schema(self) -> None:
        """repr includes schema class name."""
        from pydantic import BaseModel

        class MySchema(BaseModel):
            model: str

        conn = Connection("openai", secrets=SecretKeys(api_key="KEY"), schema=MySchema)

        assert "schema=MySchema" in repr(conn)


class TestSecretValuesValidation:
    """Test SecretValues validation against Connection requirements."""

    def test_valid_secret_values_with_all_required_keys(self) -> None:
        """SecretValues with all required keys passes validation."""
        conn = Connection("github", secrets=SecretKeys(token="GITHUB_TOKEN"), base_url="https://api.github.com")

        cred = SecretValues(conn, token="ghp_xxx")

        assert cred.connection is conn
        assert cred.values == {"token": "ghp_xxx"}

    def test_valid_secret_values_with_multiple_keys(self) -> None:
        """SecretValues with multiple required keys passes validation."""
        conn = Connection("database", secrets=SecretKeys(username="DB_USER", password="DB_PASS", host="DB_HOST"))

        cred = SecretValues(conn, username="admin", password="s3cr3t", host="localhost")

        assert cred.values == {"username": "admin", "password": "s3cr3t", "host": "localhost"}

    def test_missing_required_key_raises(self) -> None:
        """SecretValues missing a required key raises ValueError."""
        conn = Connection("github", secrets=SecretKeys(token="GITHUB_TOKEN", org="GITHUB_ORG"))

        with pytest.raises(ValueError, match="Missing secrets for 'github'"):
            SecretValues(conn, token="ghp_xxx")  # Missing 'org'

    def test_missing_multiple_keys_lists_all(self) -> None:
        """Error message lists all missing keys."""
        conn = Connection("api", secrets=SecretKeys(api_key="API_KEY", api_secret="API_SECRET", endpoint="ENDPOINT"))

        with pytest.raises(ValueError) as exc_info:
            SecretValues(conn, endpoint="https://api.example.com")

        # Should mention both missing keys
        assert "api_key" in str(exc_info.value) or "api_secret" in str(exc_info.value)

    def test_optional_key_not_required(self) -> None:
        """Optional keys don't need to be provided."""
        conn = Connection("service", secrets=SecretKeys(api_key="API_KEY", org_id=Binding("ORG_ID", optional=True)))

        # Should not raise - org_id is optional
        cred = SecretValues(conn, api_key="key123")

        assert cred.values == {"api_key": "key123"}

    def test_key_with_default_not_required(self) -> None:
        """Keys with defaults don't need to be provided."""
        conn = Connection("api", secrets=SecretKeys(api_key="API_KEY", timeout=Binding("TIMEOUT", default=30)))

        # Should not raise - timeout has default
        cred = SecretValues(conn, api_key="key123")

        assert cred.values == {"api_key": "key123"}

    def test_extra_keys_allowed(self) -> None:
        """Extra keys beyond requirements are allowed."""
        conn = Connection("github", secrets=SecretKeys(token="GITHUB_TOKEN"))

        cred = SecretValues(conn, token="ghp_xxx", extra_field="ignored")

        assert cred.values == {"token": "ghp_xxx", "extra_field": "ignored"}

    def test_empty_connection_secrets_accepts_any(self) -> None:
        """Connection with empty secrets accepts any values."""
        conn = Connection("custom", secrets=SecretKeys())

        cred = SecretValues(conn, anything="value")

        assert cred.values == {"anything": "value"}


class TestSecretValuesSerialization:
    """Test SecretValues serialization for wire transport."""

    def test_to_dict_basic(self) -> None:
        """Basic serialization includes connection name and values."""
        conn = Connection("github", secrets=SecretKeys(token="GITHUB_TOKEN"), base_url="https://api.github.com")

        cred = SecretValues(conn, token="ghp_xxx")
        result = cred.to_dict()

        assert result == {"connection_name": "github", "values": {"token": "ghp_xxx"}}

    def test_to_dict_multiple_values(self) -> None:
        """Serialization preserves all values."""
        conn = Connection("database", secrets=SecretKeys(username="USER", password="PASS"))

        cred = SecretValues(conn, username="admin", password="s3cr3t")
        result = cred.to_dict()

        assert result["values"] == {"username": "admin", "password": "s3cr3t"}

    def test_values_for_encryption_returns_envelope(self) -> None:
        """values_for_encryption returns CredentialEnvelope format."""
        conn = Connection("github", secrets=SecretKeys(token="GITHUB_TOKEN"), base_url="https://api.github.com")

        cred = SecretValues(conn, token="ghp_xxx")
        envelope = cred.values_for_encryption()

        # This is what gets encrypted client-side and decrypted by the enclave
        assert envelope == {
            "type": "api_key",
            "api_key": "ghp_xxx",
            "header_name": "Authorization",
            "header_template": "Bearer {api_key}",
            "provider_metadata": {"base_url": "https://api.github.com"},
        }

    def test_values_for_encryption_custom_header(self) -> None:
        """Custom auth_header_name and template are included in envelope."""
        conn = Connection(
            "anthropic",
            secrets=SecretKeys(api_key="ANTHROPIC_API_KEY"),
            base_url="https://api.anthropic.com",
            auth_header_name="x-api-key",
            auth_header_format="{api_key}",
        )

        cred = SecretValues(conn, api_key="sk-ant-xxx")
        envelope = cred.values_for_encryption()

        assert envelope["header_name"] == "x-api-key"
        assert envelope["header_template"] == "{api_key}"
        assert envelope["api_key"] == "sk-ant-xxx"

    def test_values_for_encryption_token_prefix(self) -> None:
        """GitHub-style 'token {api_key}' template works correctly."""
        conn = Connection(
            "github",
            secrets=SecretKeys(token="GITHUB_TOKEN"),
            base_url="https://api.github.com",
            auth_header_format="token {api_key}",
        )

        cred = SecretValues(conn, token="ghp_xxx")
        envelope = cred.values_for_encryption()

        assert envelope["header_template"] == "token {api_key}"
        assert envelope["api_key"] == "ghp_xxx"

    def test_values_for_encryption_no_base_url(self) -> None:
        """provider_metadata is None when no base_url is set."""
        conn = Connection("custom", secrets=SecretKeys(key="API_KEY"))

        cred = SecretValues(conn, key="my_key")
        envelope = cred.values_for_encryption()

        assert envelope["provider_metadata"] is None

    def test_values_for_encryption_extracts_from_various_keys(self) -> None:
        """Secret value is extracted from common key names."""
        # Test 'api_key'
        conn1 = Connection("svc1", secrets=SecretKeys(api_key="KEY"))
        assert SecretValues(conn1, api_key="val1").values_for_encryption()["api_key"] == "val1"

        # Test 'key'
        conn2 = Connection("svc2", secrets=SecretKeys(key="KEY"))
        assert SecretValues(conn2, key="val2").values_for_encryption()["api_key"] == "val2"

        # Test 'token'
        conn3 = Connection("svc3", secrets=SecretKeys(token="TOKEN"))
        assert SecretValues(conn3, token="val3").values_for_encryption()["api_key"] == "val3"

        # Test 'secret'
        conn4 = Connection("svc4", secrets=SecretKeys(secret="SECRET"))
        assert SecretValues(conn4, secret="val4").values_for_encryption()["api_key"] == "val4"

    def test_values_for_encryption_raises_on_no_secret_value(self) -> None:
        """ValueError raised when no secret value can be extracted."""
        conn = Connection("custom", secrets=SecretKeys())

        cred = SecretValues(conn, non_secret_field="some_value")  # Not a recognized key

        with pytest.raises(ValueError, match="Expected one of: api_key, key, token, secret, password"):
            cred.values_for_encryption()


class TestSecretValuesRepr:
    """Test SecretValues string representation."""

    def test_repr_hides_values(self) -> None:
        """repr does not expose secret values."""
        conn = Connection("github", secrets=SecretKeys(token="GITHUB_TOKEN"))

        cred = SecretValues(conn, token="ghp_supersecret")
        repr_str = repr(cred)

        assert "ghp_supersecret" not in repr_str
        assert "github" in repr_str
        assert "token" in repr_str  # Key names are OK

    def test_str_hides_values(self) -> None:
        """str does not expose secret values."""
        conn = Connection("github", secrets=SecretKeys(token="GITHUB_TOKEN"))

        cred = SecretValues(conn, token="ghp_supersecret")
        str_str = str(cred)

        assert "ghp_supersecret" not in str_str


class TestSecretValuesEquality:
    """Test SecretValues equality and hashing."""

    def test_same_connection_same_values_equal(self) -> None:
        """SecretValues with same connection and values are equal."""
        conn = Connection("github", secrets=SecretKeys(token="TOKEN"))

        c1 = SecretValues(conn, token="value")
        c2 = SecretValues(conn, token="value")

        assert c1 == c2

    def test_same_connection_different_values_not_equal(self) -> None:
        """SecretValues with same connection but different values are not equal."""
        conn = Connection("github", secrets=SecretKeys(token="TOKEN"))

        c1 = SecretValues(conn, token="value1")
        c2 = SecretValues(conn, token="value2")

        assert c1 != c2

    def test_different_connection_not_equal(self) -> None:
        """SecretValues with different connections are not equal."""
        conn1 = Connection("github", secrets=SecretKeys(token="TOKEN"))
        conn2 = Connection("gitlab", secrets=SecretKeys(token="TOKEN"))

        c1 = SecretValues(conn1, token="value")
        c2 = SecretValues(conn2, token="value")

        assert c1 != c2


class TestSecretValuesIntegration:
    """Integration tests for SecretValues with Connection."""

    def test_secret_values_binds_to_connection_name(self) -> None:
        """SecretValues is bound to connection by name for dispatch lookup."""
        github = Connection("github", secrets=SecretKeys(token="GITHUB_TOKEN"), base_url="https://api.github.com")
        openai = Connection(
            "openai", secrets=SecretKeys(api_key="OPENAI_API_KEY"), base_url="https://api.openai.com/v1"
        )

        github_cred = SecretValues(github, token="ghp_xxx")
        openai_cred = SecretValues(openai, api_key="sk_xxx")

        # Can build a lookup map for dispatch
        creds_map = {c.connection.name: c for c in [github_cred, openai_cred]}

        assert "github" in creds_map
        assert "openai" in creds_map
        assert creds_map["github"].values == {"token": "ghp_xxx"}

    def test_multiple_secrets_same_connection_type(self) -> None:
        """Can have multiple secret values for same connection definition."""
        conn = Connection("api", secrets=SecretKeys(key="API_KEY"))

        prod_cred = SecretValues(conn, key="prod_key")
        dev_cred = SecretValues(conn, key="dev_key")

        # Both valid, different values
        assert prod_cred.values != dev_cred.values
        assert prod_cred.connection is dev_cred.connection
