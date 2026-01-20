# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Internal models used by the dependency resolver."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any


class DependencyResolutionError(Exception):
    """Raised when a dependency cannot be resolved."""


class CircularDependencyError(DependencyResolutionError):
    """Raised when circular dependencies are detected."""


@dataclass(frozen=True)
class DependencyCall:
    """Represents a dependency callable and its nested dependencies.

    The context_param_name field stores the parameter name for auto-injecting
    the Context object at resolution time.
    """

    callable: Callable[..., Any]
    dependencies: Sequence[DependencyCall] = field(default_factory=tuple)
    use_cache: bool = True
    context_param_name: str | None = None


@dataclass
class ResolvedDependency:
    """Holds the cached value of a dependency for the current scope."""

    value: Any


CacheKey = tuple[int, ...]
