# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Connection definition framework for Dedalus MCP.

This module provides a declarative schema for defining connection types that
tools can accept. Connection definitions specify the parameters and authentication
methods required to establish connections to external services.

Key components:

* :class:`ConnectorDefinition` – Declarative schema for connection types
* :func:`define` – Factory for creating connection type handles
* :class:`ConnectorHandle` – Runtime representation of an active connection
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, TypedDict, TypeVar, cast

from pydantic import BaseModel, create_model

if TYPE_CHECKING:
    from .drivers import Driver

_UNSET = object()


# =============================================================================
# Credential Envelope Types (for enclave consumption)
# =============================================================================


class ProviderMetadata(TypedDict, total=False):
    """Provider metadata for credential envelope."""

    base_url: str | None


class ApiKeyCredentialEnvelope(TypedDict):
    """API key credential envelope for enclave decryption.

    This is the format that gets encrypted and stored. The enclave parses this
    to build the authentication header for downstream HTTP requests.

    See: dcs/apps/openmcp_as_internal/docs/EXECSPEC-credential-envelope.md
    """

    type: Literal["api_key"]
    api_key: str
    header_name: str
    header_template: str
    provider_metadata: ProviderMetadata | None


class OAuth2CredentialEnvelope(TypedDict):
    """OAuth2 credential envelope for enclave decryption."""

    type: Literal["oauth2"]
    access_token: str
    token_type: str
    provider_metadata: ProviderMetadata | None


# Union type for any credential envelope
CredentialEnvelope = ApiKeyCredentialEnvelope | OAuth2CredentialEnvelope


@dataclass(frozen=True, slots=True)
class ConnectorDefinition:
    """Declarative schema defining a connection type.

    A connection definition specifies the structure and requirements for
    establishing connections to external services.

    Attributes:
        kind: Unique identifier for the connection type (e.g., "supabase", "postgres")
        params: Parameter names and their expected types
        auth_methods: Supported authentication method names
        description: Human-readable description of the connection
    """

    kind: str
    params: dict[str, type]
    auth_methods: list[str]
    description: str = ''

    def __post_init__(self) -> None:
        """Validate connection definition invariants."""
        if not self.kind:
            raise ValueError('kind must be non-empty')
        if not self.params:
            raise ValueError('params must contain at least one parameter')
        if not self.auth_methods:
            raise ValueError('auth_methods must contain at least one method')

        # Validate param types
        for param_name, param_type in self.params.items():
            if not isinstance(param_type, type):
                raise TypeError(
                    f"param '{param_name}' must be a type, got {type(param_type).__name__}"
                )

    def to_json(self) -> dict[str, Any]:
        """Serialize to JSON for .well-known endpoint.

        Returns:
            JSON-serializable dictionary representation
        """
        return {
            'kind': self.kind,
            'params': {
                name: _type_to_json_schema(typ) for name, typ in self.params.items()
            },
            'auth_methods': self.auth_methods,
            'description': self.description,
        }


@dataclass(frozen=True, slots=True)
class ConnectorHandle:
    """Runtime handle representing an active connection.

    This is the runtime representation passed to tools at execution time,
    containing the actual configuration and credentials.

    Attributes:
        id: Unique connection identifier (format: "ddls:conn_...")
        kind: Connection type (must match a ConnectorDefinition.kind)
        config: Connection configuration parameters
        auth_type: Authentication method being used
    """

    id: str
    kind: str
    config: dict[str, Any]
    auth_type: str

    def __post_init__(self) -> None:
        """Validate connection handle invariants."""
        if not self.id.startswith('ddls:conn_'):
            raise ValueError(f"id must start with 'ddls:conn_', got {self.id}")
        if not self.kind:
            raise ValueError('kind must be non-empty')
        if not self.config:
            raise ValueError('config must be non-empty')
        if not self.auth_type:
            raise ValueError('auth_type must be non-empty')


# Type variable for connection handles
ConnT = TypeVar('ConnT', bound=ConnectorHandle)


def _model_name(kind: str, suffix: str) -> str:
    parts = [part for part in kind.replace('_', '-').split('-') if part]
    base = ''.join(part.capitalize() for part in parts) or 'Connector'
    return f'{base}{suffix}'


class _ConnectorType:
    """Type marker for connection definitions.

    This class represents a connection type that can be used in tool signatures.
    It wraps a ConnectorDefinition and can be used for type hints and validation.
    """

    _config_model: type[BaseModel]

    def __init__(self, definition: ConnectorDefinition) -> None:
        self._definition = definition
        fields = {
            name: (param_type, ...) for name, param_type in definition.params.items()
        }
        # mypy can't understand **dict spread in create_model
        self._config_model = cast(
            type[BaseModel],
            create_model(  # type: ignore[call-overload]
                _model_name(definition.kind, 'Config'),
                __base__=BaseModel,
                **fields,
            ),
        )

    @property
    def definition(self) -> ConnectorDefinition:
        """Access the underlying connection definition."""
        return self._definition

    @property
    def config_model(self) -> type[BaseModel]:
        """Return the Pydantic model for this connector's configuration."""

        return self._config_model

    def parse_config(self, data: dict[str, Any]) -> BaseModel:
        """Parse configuration payload into the typed model."""

        return self._config_model(**data)

    def validate(self, handle: ConnectorHandle) -> None:
        """Validate a connection handle against this definition.

        Args:
            handle: Connection handle to validate

        Raises:
            ValueError: If handle doesn't match definition requirements
        """
        if handle.kind != self._definition.kind:
            raise ValueError(
                f"expected kind '{self._definition.kind}', got '{handle.kind}'"
            )

        # Validate all required params are present
        missing = set(self._definition.params.keys()) - set(handle.config.keys())
        if missing:
            raise ValueError(f'missing required params: {", ".join(sorted(missing))}')

        # Validate auth method is supported
        if handle.auth_type not in self._definition.auth_methods:
            raise ValueError(
                f"auth_type '{handle.auth_type}' not in supported methods: {', '.join(self._definition.auth_methods)}"
            )

        # Validate param types
        for param_name, expected_type in self._definition.params.items():
            value = handle.config[param_name]
            if not isinstance(value, expected_type):
                raise TypeError(
                    f"param '{param_name}' expected {expected_type.__name__}, got {type(value).__name__}"
                )

    def __repr__(self) -> str:
        return f'ConnectionType(kind={self._definition.kind!r})'


def define(
    kind: str,
    params: dict[str, type],
    auth: list[str],
    description: str = '',
) -> _ConnectorType:
    """Define a connection type for use in tool signatures.

    This factory function creates a reusable connection type that can be used
    in tool parameter type hints to declare connection dependencies.

    Args:
        kind: Unique connection type identifier
        params: Dictionary mapping parameter names to their types
        auth: List of supported authentication method names
        description: Optional human-readable description

    Returns:
        Connection type handle for use in type signatures

    Example:
        >>> HttpConn = define(
        ...     kind="http-api",
        ...     params={"base_url": str},
        ...     auth=["service_credential", "user_token"],
        ...     description="Generic HTTP API connection"
        ... )
        >>> # Use in tool signature:
        >>> def my_tool(conn: HttpConn) -> str:
        ...     return "connected"
    """
    definition = ConnectorDefinition(
        kind=kind,
        params=params,
        auth_methods=auth,
        description=description,
    )
    return _ConnectorType(definition)


def _type_to_json_schema(typ: type) -> dict[str, str]:
    """Convert Python type to JSON Schema type representation.

    Args:
        typ: Python type to convert

    Returns:
        JSON Schema type dictionary
    """
    type_map: dict[type, str] = {
        str: 'string',
        int: 'integer',
        float: 'number',
        bool: 'boolean',
    }

    json_type = type_map.get(typ, 'string')
    return {'type': json_type}


__all__ = [
    # Credential envelope types (for enclave consumption)
    'ProviderMetadata',
    'ApiKeyCredentialEnvelope',
    'OAuth2CredentialEnvelope',
    'CredentialEnvelope',
    # Connection & Secrets classes
    'Connection',
    'SecretKeys',
    'SecretValues',
    # Legacy/internal types
    'Binding',
    'ConnectorDefinition',
    'ConnectorHandle',
    'EnvironmentCredentials',
    'EnvironmentCredentialLoader',
    'ResolvedConnector',
    'define',
]


# =============================================================================
# Connection - High-level abstraction for MCP server authors
# =============================================================================


class Connection:
    """Named connection to an external service.

    MCP server authors use this to declare what external services their server
    needs. The framework resolves logical names to connection handles at runtime.

    Attributes:
        name: Logical name (e.g., "github", "openai"). Used in dispatch() calls.
        secrets: Mapping from secret fields to their sources (e.g., env var names).
        schema: Optional Pydantic model for connection config validation.
        base_url: Override default base URL (for enterprise/self-hosted).
        timeout_ms: Default request timeout in milliseconds.
        auth_header_name: HTTP header name for auth (default: "Authorization").
        auth_header_format: Format string for header value (default: "Bearer {api_key}").

    Example:
        >>> # Simple connection (secrets only)
        >>> github = Connection(
        ...     "github",
        ...     secrets=SecretKeys(token="GITHUB_TOKEN"),
        ... )
        >>>
        >>> # With typed schema (recommended)
        >>> class OpenAISchema(BaseModel):
        ...     model: str = "gpt-4"
        ...     temperature: float = 0.7
        >>>
        >>> openai = Connection(
        ...     "openai",
        ...     secrets=SecretKeys(api_key="OPENAI_API_KEY"),
        ...     schema=OpenAISchema,
        ...     base_url="https://api.openai.com/v1",
        ... )
        >>>
        >>> # With dict schema (escape hatch for prototyping)
        >>> anthropic = Connection(
        ...     "anthropic",
        ...     secrets=SecretKeys(api_key="ANTHROPIC_API_KEY"),
        ...     schema={"model": str, "max_tokens": int},
        ... )
        >>>
        >>> # Custom auth header (e.g., Supabase uses 'apikey' header)
        >>> supabase = Connection(
        ...     "supabase",
        ...     secrets=SecretKeys(key="SUPABASE_SECRET_KEY"),
        ...     base_url="https://xxx.supabase.co/rest/v1",
        ...     auth_header_name="apikey",
        ...     auth_header_format="{api_key}",
        ... )
    """

    __slots__ = (
        '_name',
        '_secrets',
        '_schema',
        '_base_url',
        '_timeout_ms',
        '_auth_header_name',
        '_auth_header_format',
    )

    def __init__(
        self,
        name: str,
        secrets: SecretKeys | dict[str, Any],
        *,
        schema: type[BaseModel] | dict[str, type] | None = None,
        base_url: str | None = None,
        timeout_ms: int = 30_000,
        auth_header_name: str = 'Authorization',
        auth_header_format: str = 'Bearer {api_key}',
    ) -> None:
        """Create a named connection.

        Args:
            name: Logical name for this connection. Must be unique within a server.
            secrets: Secret key bindings. Can be SecretKeys or a dict.
            schema: Optional config schema. Pass a Pydantic BaseModel subclass
                for full type safety (recommended), or a dict mapping field names
                to types for prototyping. If None, no config validation is performed.
            base_url: Optional base URL override. If None, uses provider default.
            timeout_ms: Default timeout for requests (1000-300000 ms).
            auth_header_name: HTTP header name for authentication.
                Defaults to "Authorization". Use "apikey" for Supabase, etc.
            auth_header_format: Format string for the header value. Use {api_key}
                as placeholder for the secret value. Defaults to "Bearer {api_key}".
                Examples: "{api_key}" (raw), "token {api_key}" (GitHub), "Basic {api_key}".

        Raises:
            ValueError: If name is empty or timeout_ms is out of range.
        """
        if not name:
            raise ValueError('Connection name must be non-empty')
        if not (1000 <= timeout_ms <= 300_000):
            raise ValueError(f'timeout_ms must be 1000-300000, got {timeout_ms}')
        if '{api_key}' not in auth_header_format:
            raise ValueError("auth_header_format must contain '{api_key}' placeholder")

        self._name = name
        self._secrets = (
            secrets
            if isinstance(secrets, SecretKeys)
            else SecretKeys(**secrets)
        )
        self._schema = self._resolve_schema(name, schema)
        self._base_url = base_url
        self._timeout_ms = timeout_ms
        self._auth_header_name = auth_header_name
        self._auth_header_format = auth_header_format

    @staticmethod
    def _resolve_schema(
        name: str,
        schema: type[BaseModel] | dict[str, type] | None,
    ) -> type[BaseModel] | None:
        """Resolve schema to a Pydantic model class.

        Args:
            name: Connection name (used for dynamic model naming).
            schema: User-provided schema (BaseModel subclass, dict, or None).

        Returns:
            Pydantic model class, or None if no schema provided.
        """
        if schema is None:
            return None
        if isinstance(schema, type) and issubclass(schema, BaseModel):
            return schema
        if isinstance(schema, dict):
            # Escape hatch: create dynamic model from dict
            # mypy can't understand **dict spread in create_model
            fields = {field: (field_type, ...) for field, field_type in schema.items()}
            return cast(
                type[BaseModel],
                create_model(  # type: ignore[call-overload]
                    f'{name.title().replace("-", "").replace("_", "")}Schema',
                    __base__=BaseModel,
                    **fields,
                ),
            )
        raise TypeError(
            f"schema must be a BaseModel subclass or dict[str, type], got {type(schema).__name__}"
        )

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
        """Validate config against the schema.

        Args:
            config: Configuration dictionary to validate.

        Returns:
            Validated Pydantic model instance.

        Raises:
            ValueError: If no schema is defined for this connection.
            ValidationError: If config doesn't match the schema.
        """
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
        result: dict[str, Any] = {
            'name': self._name,
            'secrets': self._secrets.to_dict(),
        }
        if self._schema is not None:
            result['schema'] = self._schema.__name__
        if self._base_url is not None:
            result['base_url'] = self._base_url
        if self._timeout_ms != 30_000:
            result['timeout_ms'] = self._timeout_ms
        if self._auth_header_name != 'Authorization':
            result['auth_header_name'] = self._auth_header_name
        if self._auth_header_format != 'Bearer {api_key}':
            result['auth_header_format'] = self._auth_header_format
        return result

    def __repr__(self) -> str:
        parts = [f'name={self._name!r}']
        if self._schema is not None:
            parts.append(f'schema={self._schema.__name__}')
        if self._base_url:
            parts.append(f'base_url={self._base_url!r}')
        if self._auth_header_name != 'Authorization':
            parts.append(f'auth_header_name={self._auth_header_name!r}')
        return f'Connection({", ".join(parts)})'

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Connection):
            return NotImplemented
        return self._name == other._name

    def __hash__(self) -> int:
        return hash(self._name)


@dataclass(frozen=True, slots=True)
class ResolvedConnector:
    """Typed connector resolution result.

    Attributes:
        handle: Persistable connector handle (config stored as plain dict).
        config: Typed configuration model parsed via :class:`ConnectorDefinition`.
        auth: Typed secret/authentication model including the ``type`` discriminator.
    """

    handle: ConnectorHandle
    config: BaseModel
    auth: BaseModel

    async def build_client(self, driver: 'Driver') -> Any:
        """Instantiate a client using the provided driver."""
        return await driver.create_client(
            self.config.model_dump(),
            self.auth.model_dump(),
        )


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

        result: dict[str, Any] = {'name': self.name}
        if self.cast != str:
            result['cast'] = self.cast.__name__
        if self.default is not _UNSET:
            result['default'] = self.default
        if self.optional:
            result['optional'] = True

        return result


@dataclass(frozen=True, slots=True)
class SecretKeys:
    """Schema declaring what secret fields a Connection needs.

    Maps secret field names to their sources (typically environment variable names).
    Simple strings are auto-converted to Binding objects.

    Example:
        >>> SecretKeys(token="GITHUB_TOKEN")  # simple
        >>> SecretKeys(token="GITHUB_TOKEN", org=Binding("GITHUB_ORG", optional=True))
    """

    entries: dict[str, Binding]

    def __init__(self, **kwargs: Any) -> None:
        entries = {
            key: value if isinstance(value, Binding) else Binding(str(value))
            for key, value in kwargs.items()
        }
        object.__setattr__(self, 'entries', entries)

    def to_dict(self) -> dict[str, Any]:
        """Serialize all bindings for wire transport."""
        return {key: binding.to_dict() for key, binding in self.entries.items()}




@dataclass(frozen=True, slots=True)
class EnvironmentCredentials:
    """Environment-backed configuration for a connector auth method."""

    config: SecretKeys = field(default_factory=SecretKeys)
    secrets: SecretKeys = field(default_factory=SecretKeys)


class EnvironmentCredentialLoader:
    """Load connector credentials from environment variables.

    This helper lets resource servers bootstrap connection handles without
    embedding vendor-specific logic. Each authentication method maps the
    connector's required parameters and secret fields to environment
    variables. Missing variables raise ``RuntimeError`` so misconfiguration is
    caught during startup.
    """

    def __init__(
        self,
        connector: _ConnectorType,
        variants: dict[str, EnvironmentCredentials],
        *,
        handle_prefix: str = 'ddls:conn_env',
    ) -> None:
        if not variants:
            raise ValueError('variants must contain at least one auth mapping')

        allowed_auth = set(connector.definition.auth_methods)
        unknown = sorted(set(variants.keys()) - allowed_auth)
        if unknown:
            raise ValueError(
                'environment credentials configured for unsupported auth methods: '
                + ', '.join(unknown)
            )

        self._connector = connector
        self._variants = variants
        self._handle_prefix = handle_prefix.rstrip('_')

    def supported_auth_types(self) -> list[str]:
        """Return auth types configured for this source."""
        return sorted(self._variants.keys())

    def load(self, auth_type: str) -> ResolvedConnector:
        """Load credentials for ``auth_type``.

        Returns the connector handle plus a secret payload that callers can
        hand to a driver.
        """
        if auth_type not in self._variants:
            raise ValueError(f"auth_type '{auth_type}' not configured for this source")

        mapping = self._variants[auth_type]
        config_values = {
            name: self._read_env(value)
            for name, value in mapping.config.entries.items()
        }
        config_model = self._connector.config_model(**config_values)

        secret_fields = {
            name: (value.cast, ...) for name, value in mapping.secrets.entries.items()
        }
        # mypy can't understand **dict spread in create_model
        AuthModel = cast(
            type[BaseModel],
            create_model(  # type: ignore[call-overload]
                _model_name(f'{self._connector.definition.kind}_{auth_type}', 'Auth'),
                __base__=BaseModel,
                type=(Literal[auth_type], auth_type),
                **secret_fields,
            ),
        )
        secret_values = {
            name: self._read_env(value)
            for name, value in mapping.secrets.entries.items()
        }
        auth_model = AuthModel(**secret_values)

        handle = ConnectorHandle(
            id=f'{self._handle_prefix}_{self._connector.definition.kind}_{auth_type}',
            kind=self._connector.definition.kind,
            config=config_model.model_dump(),
            auth_type=auth_type,
        )
        self._connector.validate(handle)

        return ResolvedConnector(handle=handle, config=config_model, auth=auth_model)

    @staticmethod
    def _read_env(binding: Binding) -> Any:
        raw = os.getenv(binding.name)
        if raw is None or raw == '':
            if binding.default is not _UNSET:
                return binding.default
            if binding.optional:
                return None
            raise RuntimeError(f'Environment variable {binding.name} is not set')
        if binding.cast is str:
            return raw
        return binding.cast(raw)


# --- SecretValues: Binds actual secret values to Connection definitions ---


class SecretValues:
    """Bind actual secret values to a Connection definition.

    MCP server authors use Connection to declare what secrets their server
    needs. SDK users use SecretValues to provide the actual values at runtime.

    The SecretValues class validates that all required keys from the Connection's
    secrets are provided, failing fast with clear error messages.

    Attributes:
        connection: The Connection this binds to.
        values: The actual secret values (keys match Connection.secrets entries).

    Example:
        >>> github = Connection("github", secrets=SecretKeys(token="GITHUB_TOKEN"))
        >>> github_secrets = SecretValues(github, token="ghp_xxx")
        >>> # Use in SDK initialization:
        >>> client = Dedalus(api_key="dsk_...", secrets=[github_secrets])
    """

    __slots__ = ('_connection', '_values')

    def __init__(self, connection: Connection, **values: Any) -> None:
        """Create a secret binding for a connection.

        Args:
            connection: The Connection definition this satisfies.
            **values: Keyword arguments mapping secret keys to values.
                      Keys must match entries in connection.secrets.

        Raises:
            ValueError: If required keys from connection.secrets are missing.
        """
        # Compute required keys: not optional and no default
        required_keys = {
            key
            for key, binding in connection.secrets.entries.items()
            if not binding.optional and binding.default is _UNSET
        }

        provided_keys = set(values.keys())
        missing = required_keys - provided_keys

        if missing:
            raise ValueError(
                f"Missing secrets for '{connection.name}': {sorted(missing)}"
            )

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
        """Return credential envelope for client-side encryption.

        Builds the CredentialEnvelope format expected by the enclave. The enclave
        decrypts this JSON and uses header_template to build the auth header.

        Returns:
            ApiKeyCredentialEnvelope with type, api_key, header_name, header_template,
            and provider_metadata fields.

        Raises:
            ValueError: If no credential value can be extracted from the provided values.
        """
        # Extract credential value from known key names (in priority order)
        CREDENTIAL_KEYS = ('api_key', 'key', 'token', 'secret', 'password')
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

        # Build provider metadata
        provider_metadata: ProviderMetadata | None = None
        if self._connection.base_url:
            provider_metadata = {'base_url': self._connection.base_url}

        return {
            'type': 'api_key',
            'api_key': api_key,
            'header_name': self._connection.auth_header_name,
            'header_template': self._connection.auth_header_format,  # Wire format uses 'header_template'
            'provider_metadata': provider_metadata,
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize for wire transport or debugging.

        Note: This includes credential values. Use with caution.
        """
        return {
            'connection_name': self._connection.name,
            'values': dict(self._values),
        }

    def __repr__(self) -> str:
        """String representation (hides secret values)."""
        keys = list(self._values.keys())
        return f'SecretValues({self._connection.name!r}, keys={keys})'

    def __str__(self) -> str:
        """String representation (hides secret values)."""
        return repr(self)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SecretValues):
            return NotImplemented
        return (
            self._connection.name == other._connection.name
            and self._values == other._values
        )

    def __hash__(self) -> int:
        # Values are mutable dicts, so we can't include them in hash
        # Hash by connection name only
        return hash(self._connection.name)
