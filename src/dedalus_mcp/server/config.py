# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Server configuration dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from .notifications import NotificationSink
    from ..types.shared.capabilities import Icon


@dataclass(slots=True, frozen=True)
class SamplingConfig:
    """Configuration for the sampling service.

    Sampling allows the server to request LLM completions from the client.
    These parameters control timeouts, concurrency, and circuit-breaker behavior.

    See: https://modelcontextprotocol.io/specification/2025-06-18/client/sampling
    """

    timeout: float = 60.0
    """Timeout in seconds for sampling requests."""

    max_concurrent: int = 4
    """Maximum concurrent sampling requests per session."""

    failure_threshold: int = 3
    """Consecutive failures before entering cooldown."""

    cooldown_seconds: float = 30.0
    """Cooldown duration after hitting failure threshold."""


@dataclass(slots=True, frozen=True)
class ElicitationConfig:
    """Configuration for the elicitation service.

    Elicitation allows the server to request structured input from the user.

    See: https://modelcontextprotocol.io/specification/2025-06-18/client/elicitation
    """

    timeout: float = 60.0
    """Timeout in seconds for elicitation requests."""


@dataclass(slots=True, frozen=True)
class PingConfig:
    """Configuration for the ping/health service.

    The phi accrual failure detector tracks session liveness.

    See: https://modelcontextprotocol.io/specification/2025-06-18/basic/utilities/ping
    """

    phi_threshold: float = 5.0
    """Default phi threshold for failure detection."""


@dataclass(slots=True)
class ServerConfig:
    """Tunable parameters for MCPServer.

    All fields have sane defaults. Override only what you need.

    Example:
        >>> from dedalus_mcp.server import ServerConfig, SamplingConfig
        >>>
        >>> # Simple override
        >>> config = ServerConfig(pagination_limit=100)
        >>>
        >>> # With nested config
        >>> config = ServerConfig(
        ...     pagination_limit=100,
        ...     sampling=SamplingConfig(timeout=120.0, max_concurrent=8),
        ... )
    """

    # Nested configs for multi-param groups
    sampling: SamplingConfig = field(default_factory=SamplingConfig)
    """Sampling service configuration."""

    elicitation: ElicitationConfig = field(default_factory=ElicitationConfig)
    """Elicitation service configuration."""

    ping: PingConfig = field(default_factory=PingConfig)
    """Ping/health service configuration."""

    # Flat params for standalone values
    pagination_limit: int = 50
    """Page size for list operations (tools, resources, prompts)."""

    completion_limit: int = 100
    """Maximum completions returned by completion/complete."""

    # Custom components (power users)
    notification_sink: NotificationSink | None = None
    """Custom notification sink. Defaults to direct session delivery."""

    icons: list[Icon] | None = None
    """Server icons for client display."""


__all__ = ["SamplingConfig", "ElicitationConfig", "PingConfig", "ServerConfig"]
