# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Connection and credential types for MCP servers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from pydantic import BaseModel, create_model

from .envelope import ApiKeyCredentialEnvelope, ProviderMetadata


_UNSET = object()


# =============================================================================
# Binding & SecretKeys
# =============================================================================


@dataclass(frozen=True, slots=True)
class Binding:
    """Single credential field binding with options.

    Maps a credential field name to its source (typically an environment variable).
    Use this when you need optional fields, defaults, or type casting.

    Example:
        >>> Binding("GITHUB_TOKEN")  # simple
        >>> Binding("TIMEOUT", cast=int, default=30)  # with options
        >>> Binding("WORKSPACE", optional=True)  # optional field
    """

    name: str
    cast: type = str
    default: Any = _UNSET
    optional: bool = False

    def to_dict(self) -> dict[str, Any] | str:
        """Serialize binding for wire transport."""
        has_options = self.cast != str or self.default is not _UNSET or self.optional

        if not has_options:
            return self.name

        result: dict[str, Any] = {"name": self.name}
        if self.cast != str:
            result["cast"] = self.cast.__name__
        if self.default is not _UNSET:
            result["default"] = self.default
        if self.optional:
            result["optional"] = True

        return result


@dataclass(frozen=True, slots=True)
class SecretKeys:
    """Schema declaring what secret fields a Connection needs.

    Maps secret field names to their sources (typically environment variable names).
    Simple strings are auto-converted to Binding objects.

    Example:
        >>> SecretKeys(token="GITHUB_TOKEN")  # simple
        >>> SecretKeys(
        ...     token="GITHUB_TOKEN", org=Binding("GITHUB_ORG", optional=True)
        ... )
    """

    entries: dict[str, Binding]

    def __init__(self, **kwargs: Any) -> None:
        entries = {key: value if isinstance(value, Binding) else Binding(str(value)) for key, value in kwargs.items()}
        object.__setattr__(self, "entries", entries)

    def to_dict(self) -> dict[str, Any]:
        """Serialize all bindings for wire transport."""
        return {key: binding.to_dict() for key, binding in self.entries.items()}


# =============================================================================
# Connection
# =============================================================================


class Connection:
    """Connection to an external service.

    MCP server authors use this to declare what external services their server
    needs. The framework resolves logical names to connection handles at runtime.

    For single-connection servers using auto-dispatch, the `name` parameter is
    optional. Multi-connection servers must provide unique names.

    Attributes:
        name: Logical name (e.g., "github", "openai"). Used in dispatch() calls.
              Optional for single-connection servers using auto-dispatch.
        secrets: Mapping from secret fields to their sources (e.g., env var names).
        schema: Optional Pydantic model for connection config validation.
        base_url: Override default base URL (for enterprise/self-hosted).
        timeout_ms: Default request timeout in milliseconds.
        auth_header_name: HTTP header name for auth (default: "Authorization").
        auth_header_format: Format string for header value (default: "Bearer {api_key}").

    Example:
        >>> # Single-connection (name optional)
        >>> gmail = Connection(secrets=SecretKeys(token="GMAIL_TOKEN"))
        >>> # Multi-connection (names required)
        >>> github = Connection(name="github", secrets=SecretKeys(token="GITHUB_TOKEN"))
        >>> slack = Connection("slack", secrets=SecretKeys(token="SLACK_TOKEN"))
    """

    __slots__ = ("_name", "_secrets", "_schema", "_base_url", "_timeout_ms", "_auth_header_name", "_auth_header_format")

    def __init__(
        self,
        name: str = "",
        *,
        secrets: SecretKeys | dict[str, Any],
        schema: type[BaseModel] | dict[str, type] | None = None,
        base_url: str | None = None,
        timeout_ms: int = 30_000,
        auth_header_name: str = "Authorization",
        auth_header_format: str = "Bearer {api_key}",
    ) -> None:
        """Create a connection.

        Args:
            name: Logical name for this connection. Required for multi-connection
                  servers, optional for single-connection servers using auto-dispatch.
            secrets: Secret key bindings. Can be SecretKeys or a dict. Required.
            schema: Optional config schema (BaseModel subclass or dict[str, type]).
            base_url: Optional base URL override.
            timeout_ms: Default timeout for requests (1000-300000 ms).
            auth_header_name: HTTP header name for authentication.
            auth_header_format: Format string for the header value ({api_key} placeholder).

        Raises:
            ValueError: If timeout_ms is out of range.
        """
        if not (1000 <= timeout_ms <= 300_000):
            raise ValueError(f"timeout_ms must be 1000-300000, got {timeout_ms}")
        if "{api_key}" not in auth_header_format:
            raise ValueError("auth_header_format must contain '{api_key}' placeholder")

        self._name = name
        self._secrets = secrets if isinstance(secrets, SecretKeys) else SecretKeys(**secrets)
        self._schema = self._resolve_schema(name, schema)
        self._base_url = base_url
        self._timeout_ms = timeout_ms
        self._auth_header_name = auth_header_name
        self._auth_header_format = auth_header_format

    @staticmethod
    def _resolve_schema(name: str, schema: type[BaseModel] | dict[str, type] | None) -> type[BaseModel] | None:
        """Resolve schema to a Pydantic model class."""
        if schema is None:
            return None
        if isinstance(schema, type) and issubclass(schema, BaseModel):
            return schema
        if isinstance(schema, dict):
            fields = {field: (field_type, ...) for field, field_type in schema.items()}
            model_name = name.title().replace("-", "").replace("_", "") if name else "Connection"
            return cast(
                type[BaseModel],
                create_model(  # type: ignore[call-overload]
                    f"{model_name}Schema", __base__=BaseModel, **fields
                ),
            )
        raise TypeError(f"schema must be a BaseModel subclass or dict[str, type], got {type(schema).__name__}")

    @property
    def name(self) -> str:
        """Logical name of this connection."""
        return self._name

    @property
    def secrets(self) -> SecretKeys:
        """Secret key bindings for this connection."""
        return self._secrets

    @property
    def schema(self) -> type[BaseModel] | None:
        """Pydantic model for config validation, or None if no schema."""
        return self._schema

    def validate_config(self, config: dict[str, Any]) -> BaseModel:
        """Validate config against the schema."""
        if self._schema is None:
            raise ValueError(f"Connection '{self._name}' has no schema defined")
        return self._schema(**config)

    @property
    def base_url(self) -> str | None:
        """Base URL override, or None for provider default."""
        return self._base_url

    @property
    def timeout_ms(self) -> int:
        """Default request timeout in milliseconds."""
        return self._timeout_ms

    @property
    def auth_header_name(self) -> str:
        """HTTP header name for authentication."""
        return self._auth_header_name

    @property
    def auth_header_format(self) -> str:
        """Format string for authentication header value."""
        return self._auth_header_format

    def to_dict(self) -> dict[str, Any]:
        """Serialize for wire transport or storage."""
        result: dict[str, Any] = {"name": self._name, "secrets": self._secrets.to_dict()}
        if self._schema is not None:
            result["schema"] = self._schema.__name__
        if self._base_url is not None:
            result["base_url"] = self._base_url
        if self._timeout_ms != 30_000:
            result["timeout_ms"] = self._timeout_ms
        if self._auth_header_name != "Authorization":
            result["auth_header_name"] = self._auth_header_name
        if self._auth_header_format != "Bearer {api_key}":
            result["auth_header_format"] = self._auth_header_format
        return result

    def __repr__(self) -> str:
        parts = [f"name={self._name!r}"]
        if self._schema is not None:
            parts.append(f"schema={self._schema.__name__}")
        if self._base_url:
            parts.append(f"base_url={self._base_url!r}")
        if self._auth_header_name != "Authorization":
            parts.append(f"auth_header_name={self._auth_header_name!r}")
        return f"Connection({', '.join(parts)})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Connection):
            return NotImplemented
        return self._name == other._name

    def __hash__(self) -> int:
        return hash(self._name)


# =============================================================================
# SecretValues
# =============================================================================


class SecretValues:
    """Bind actual secret values to a Connection definition.

    SDK users use this to provide actual credential values at runtime.

    Example:
        >>> github = Connection("github", secrets=SecretKeys(token="GITHUB_TOKEN"))
        >>> secrets = SecretValues(connection=github, token="ghp_xxx")
    """

    __slots__ = ("_connection", "_values")

    def __init__(self, connection: Connection, **values: Any) -> None:
        """Create a secret binding for a connection.

        Args:
            connection: The Connection definition this satisfies.
            **values: Keyword arguments mapping secret keys to values.

        Raises:
            ValueError: If required keys from connection.secrets are missing.
        """
        required_keys = {
            key
            for key, binding in connection.secrets.entries.items()
            if not binding.optional and binding.default is _UNSET
        }
        missing = required_keys - set(values.keys())
        if missing:
            raise ValueError(f"Missing secrets for '{connection.name}': {sorted(missing)}")

        self._connection = connection
        self._values = dict(values)

    @property
    def connection(self) -> Connection:
        """The Connection this credential binds to."""
        return self._connection

    @property
    def values(self) -> dict[str, Any]:
        """The credential values (read-only copy)."""
        return dict(self._values)

    def values_for_encryption(self) -> ApiKeyCredentialEnvelope:
        """Return credential envelope for client-side encryption."""
        CREDENTIAL_KEYS = ("api_key", "key", "token", "secret", "password")
        api_key: str | None = None
        for key in CREDENTIAL_KEYS:
            if key in self._values and self._values[key]:
                api_key = str(self._values[key])
                break

        if api_key is None:
            raise ValueError(
                f"No credential value found in {list(self._values.keys())}. "
                f"Expected one of: {', '.join(CREDENTIAL_KEYS)}."
            )

        provider_metadata: ProviderMetadata | None = None
        if self._connection.base_url:
            provider_metadata = {"base_url": self._connection.base_url}

        return {
            "type": "api_key",
            "api_key": api_key,
            "header_name": self._connection.auth_header_name,
            "header_template": self._connection.auth_header_format,
            "provider_metadata": provider_metadata,
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize for wire transport (includes credential values)."""
        return {"connection_name": self._connection.name, "values": dict(self._values)}

    def __repr__(self) -> str:
        return f"SecretValues({self._connection.name!r}, keys={list(self._values.keys())})"

    def __str__(self) -> str:
        return repr(self)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SecretValues):
            return NotImplemented
        return self._connection.name == other._connection.name and self._values == other._values

    def __hash__(self) -> int:
        return hash(self._connection.name)


__all__ = [
    # Credential envelope types
    "ApiKeyCredentialEnvelope",
    "CredentialEnvelope",
    "OAuth2CredentialEnvelope",
    "ProviderMetadata",
    # User-facing types
    "Binding",
    "Connection",
    "SecretKeys",
    "SecretValues",
    # Internal sentinel used by server/connectors.py
    "_UNSET",
]
