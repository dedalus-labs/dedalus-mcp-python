# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT
"""Pytest fixtures for protocol version compliance tests."""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any, TYPE_CHECKING

import pytest
from jsonschema import Draft7Validator, RefResolver

if TYPE_CHECKING:
    from collections.abc import Callable

_SCHEMA_ROOT = Path(__file__).resolve().parent


@cache
def _load_schema(version: str) -> tuple[dict[str, Any], RefResolver]:
    folder_name = version.replace("-", "_")
    schema_path = _SCHEMA_ROOT / folder_name / "schema.json"
    if not schema_path.exists():
        msg = f"Schema file not found for protocol version {version}: {schema_path}"
        raise FileNotFoundError(msg)

    with schema_path.open("r", encoding="utf-8") as handle:
        schema = json.load(handle)

    resolver = RefResolver(base_uri=schema_path.as_uri(), referrer=schema)
    return schema, resolver


@pytest.fixture(scope="session")
def assert_schema() -> Callable[[Any, str], None]:
    """Return a helper for validating payloads against MCP JSON Schemas."""

    def _validate(instance: Any, ref: str, *, version: str) -> None:
        _, resolver = _load_schema(version)
        Draft7Validator(schema={"$ref": ref}, resolver=resolver).validate(instance)

    return _validate


__all__ = ["assert_schema"]
