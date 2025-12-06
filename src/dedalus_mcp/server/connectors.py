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
from typing import TYPE_CHECKING, Any, Literal, TypeVar

from pydantic import BaseModel, create_model

if TYPE_CHECKING:
    from .drivers import Driver

_UNSET = object()


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
    description: str = ""

    def __post_init__(self) -> None:
        """Validate connection definition invariants."""
        if not self.kind:
            raise ValueError("kind must be non-empty")
        if not self.params:
            raise ValueError("params must contain at least one parameter")
        if not self.auth_methods:
            raise ValueError("auth_methods must contain at least one method")

        # Validate param types
        for param_name, param_type in self.params.items():
            if not isinstance(param_type, type):
                raise TypeError(f"param '{param_name}' must be a type, got {type(param_type).__name__}")

    def to_json(self) -> dict[str, Any]:
        """Serialize to JSON for .well-known endpoint.

        Returns:
            JSON-serializable dictionary representation
        """
        return {
            "kind": self.kind,
            "params": {name: _type_to_json_schema(typ) for name, typ in self.params.items()},
            "auth_methods": self.auth_methods,
            "description": self.description,
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
        if not self.id.startswith("ddls:conn_"):
            raise ValueError(f"id must start with 'ddls:conn_', got {self.id}")
        if not self.kind:
            raise ValueError("kind must be non-empty")
        if not self.config:
            raise ValueError("config must be non-empty")
        if not self.auth_type:
            raise ValueError("auth_type must be non-empty")


# Type variable for connection handles
ConnT = TypeVar("ConnT", bound=ConnectorHandle)


def _model_name(kind: str, suffix: str) -> str:
    parts = [part for part in kind.replace("_", "-").split("-") if part]
    base = "".join(part.capitalize() for part in parts) or "Connector"
    return f"{base}{suffix}"


class _ConnectorType:
    """Type marker for connection definitions.

    This class represents a connection type that can be used in tool signatures.
    It wraps a ConnectorDefinition and can be used for type hints and validation.
    """

    def __init__(self, definition: ConnectorDefinition) -> None:
        self._definition = definition
        fields = {name: (param_type, ...) for name, param_type in definition.params.items()}
        self._config_model = create_model(
            _model_name(definition.kind, "Config"),
            __base__=BaseModel,
            **fields,
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
            raise ValueError(f"expected kind '{self._definition.kind}', got '{handle.kind}'")

        # Validate all required params are present
        missing = set(self._definition.params.keys()) - set(handle.config.keys())
        if missing:
            raise ValueError(f"missing required params: {', '.join(sorted(missing))}")

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
        return f"ConnectionType(kind={self._definition.kind!r})"


def define(
    kind: str,
    params: dict[str, type],
    auth: list[str],
    description: str = "",
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
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
    }

    json_type = type_map.get(typ, "string")
    return {"type": json_type}


__all__ = [
    "Connection",
    "ConnectorDefinition",
    "ConnectorHandle",
    "EnvironmentBinding",
    "EnvironmentBindings",
    "EnvironmentCredentials",
    "EnvironmentCredentialLoader",
    "ResolvedConnector",
    "define",
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
        env: Mapping from credential fields to environment variable names.
        base_url: Override default base URL (for enterprise/self-hosted).
        timeout_ms: Default request timeout in milliseconds.

    Example:
        >>> github = Connection(
        ...     "github",
        ...     env=EnvironmentBindings(token="GITHUB_TOKEN"),
        ... )
        >>> openai = Connection(
        ...     "openai",
        ...     env=EnvironmentBindings(api_key="OPENAI_API_KEY"),
        ...     base_url="https://api.openai.com/v1",
        ... )
        >>> server = MCPServer(
        ...     name="code-reviewer",
        ...     connections=[github, openai],
        ... )
    """

    __slots__ = ("_name", "_env", "_base_url", "_timeout_ms")

    def __init__(
        self,
        name: str,
        env: EnvironmentBindings | dict[str, Any],
        *,
        base_url: str | None = None,
        timeout_ms: int = 30_000,
    ) -> None:
        """Create a named connection.

        Args:
            name: Logical name for this connection. Must be unique within a server.
            env: Environment bindings for credentials. Can be EnvironmentBindings
                 or a dict that will be converted.
            base_url: Optional base URL override. If None, uses provider default.
            timeout_ms: Default timeout for requests (1000-300000 ms).

        Raises:
            ValueError: If name is empty or timeout_ms is out of range.
        """
        if not name:
            raise ValueError("Connection name must be non-empty")
        if not (1000 <= timeout_ms <= 300_000):
            raise ValueError(f"timeout_ms must be 1000-300000, got {timeout_ms}")

        self._name = name
        self._env = env if isinstance(env, EnvironmentBindings) else EnvironmentBindings(**env)
        self._base_url = base_url
        self._timeout_ms = timeout_ms

    @property
    def name(self) -> str:
        """Logical name of this connection."""
        return self._name

    @property
    def env(self) -> EnvironmentBindings:
        """Environment bindings for credentials."""
        return self._env

    @property
    def base_url(self) -> str | None:
        """Base URL override, or None for provider default."""
        return self._base_url

    @property
    def timeout_ms(self) -> int:
        """Default request timeout in milliseconds."""
        return self._timeout_ms

    def to_dict(self) -> dict[str, Any]:
        """Serialize for wire transport or storage."""
        result: dict[str, Any] = {
            "name": self._name,
            "env": self._env.to_dict(),
        }
        if self._base_url is not None:
            result["base_url"] = self._base_url
        if self._timeout_ms != 30_000:
            result["timeout_ms"] = self._timeout_ms
        return result

    def __repr__(self) -> str:
        parts = [f"name={self._name!r}"]
        if self._base_url:
            parts.append(f"base_url={self._base_url!r}")
        return f"Connection({', '.join(parts)})"

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

    async def build_client(self, driver: "Driver") -> Any:
        """Instantiate a client using the provided driver."""

        return await driver.create_client(self.config, self.auth)

@dataclass(frozen=True, slots=True)
class EnvironmentBinding:
    """Descriptor for a single environment-provided value."""

    name: str
    cast: type = str
    default: Any = _UNSET
    optional: bool = False

    def to_dict(self) -> dict[str, Any] | str:
        """Serialize binding for wire transport.

        Simple bindings (name only) serialize to string.
        Bindings with options serialize to dict.
        """
        has_options = (
            self.cast != str
            or self.default is not _UNSET
            or self.optional
        )

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
class EnvironmentBindings:
    """Mapping from field names to environment bindings."""

    entries: dict[str, EnvironmentBinding]

    def __init__(self, **kwargs: Any) -> None:  # type: ignore[override]
        entries = {
            key: value if isinstance(value, EnvironmentBinding) else EnvironmentBinding(str(value))
            for key, value in kwargs.items()
        }
        object.__setattr__(self, "entries", entries)

    def to_dict(self) -> dict[str, Any]:
        """Serialize all bindings for wire transport."""
        return {key: binding.to_dict() for key, binding in self.entries.items()}


@dataclass(frozen=True, slots=True)
class EnvironmentCredentials:
    """Environment-backed configuration for a connector auth method."""

    config: EnvironmentBindings = field(default_factory=EnvironmentBindings)
    secrets: EnvironmentBindings = field(default_factory=EnvironmentBindings)


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
        handle_prefix: str = "ddls:conn_env",
    ) -> None:
        if not variants:
            raise ValueError("variants must contain at least one auth mapping")

        allowed_auth = set(connector.definition.auth_methods)
        unknown = sorted(set(variants.keys()) - allowed_auth)
        if unknown:
            raise ValueError(
                "environment credentials configured for unsupported auth methods: "
                + ", ".join(unknown)
            )

        self._connector = connector
        self._variants = variants
        self._handle_prefix = handle_prefix.rstrip("_")

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
        config_values = {name: self._read_env(value) for name, value in mapping.config.entries.items()}
        config_model = self._connector.config_model(**config_values)

        secret_fields = {
            name: (value.cast, ...)
            for name, value in mapping.secrets.entries.items()
        }
        AuthModel = create_model(  # type: ignore[call-arg]
            _model_name(f"{self._connector.definition.kind}_{auth_type}", "Auth"),
            __base__=BaseModel,
            type=(Literal[auth_type], auth_type),
            **secret_fields,
        )
        secret_values = {name: self._read_env(value) for name, value in mapping.secrets.entries.items()}
        auth_model = AuthModel(**secret_values)

        handle = ConnectorHandle(
            id=f"{self._handle_prefix}_{self._connector.definition.kind}_{auth_type}",
            kind=self._connector.definition.kind,
            config=config_model.model_dump(),
            auth_type=auth_type,
        )
        self._connector.validate(handle)

        return ResolvedConnector(handle=handle, config=config_model, auth=auth_model)

    @staticmethod
    def _read_env(binding: EnvironmentBinding) -> Any:
        raw = os.getenv(binding.name)
        if raw is None or raw == "":
            if binding.default is not _UNSET:
                return binding.default
            if binding.optional:
                return None
            raise RuntimeError(f"Environment variable {binding.name} is not set")
        if binding.cast is str:
            return raw
        return binding.cast(raw)

