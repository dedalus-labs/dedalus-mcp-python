# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Public dependency helpers for Dedalus MCP."""

from __future__ import annotations

import inspect
from typing import Any, Callable, Sequence, get_origin

from .models import DependencyCall


def register_injectable_type(typ: type) -> None:
    """Register a type to be auto-injected in dependency resolution.

    Currently only Context is supported. This exists for future extensibility.
    """
    # For now, we only support Context, but this allows future types
    pass


def _find_context_param(func: Callable[..., Any]) -> str | None:
    """Inspect function signature to find a Context-typed parameter.

    Uses get_type_hints to properly resolve string annotations and handle
    forward references, ensuring the Context class identity check works correctly.
    """
    from typing import get_type_hints

    # Import here to avoid circular dependency
    from ...context import Context

    try:
        hints = get_type_hints(func)
    except Exception:
        # get_type_hints can fail for various reasons (missing globals, etc.)
        return None

    for param_name, param_type in hints.items():
        # Skip return type hint
        if param_name == "return":
            continue

        # Handle generic aliases (e.g., Optional[Context])
        origin = get_origin(param_type)
        resolved_type = origin if origin is not None else param_type

        if resolved_type is Context:
            return param_name

    return None


class Depends:
    """Marks a callable as a dependency to be resolved by the framework.

    Supports both explicit subdependencies and automatic injection of
    registered types (like Context) based on type annotations.
    """

    __slots__ = ("call", "dependencies", "use_cache")

    def __init__(
        self,
        dependency: Callable[..., Any],
        *subdependencies: Callable[..., Any],
        use_cache: bool = True,
    ) -> None:
        if not callable(dependency):
            raise TypeError("Depends() arguments must be callable")

        self.call: Callable[..., Any] = dependency
        self.dependencies: Sequence[Callable[..., Any]] = subdependencies
        self.use_cache: bool = use_cache

    def as_call(self) -> DependencyCall:
        nested = tuple(Depends(dep).as_call() if not isinstance(dep, Depends) else dep.as_call() for dep in self.dependencies)
        context_param_name = _find_context_param(self.call)
        return DependencyCall(self.call, nested, self.use_cache, context_param_name)


__all__ = ["Depends"]

