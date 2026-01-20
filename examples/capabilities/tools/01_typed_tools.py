# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Typed tools with automatic schema inference.

Dedalus MCP generates JSON Schema from Python type hints. Complex types,
optional parameters, defaults, and Pydantic models all work.

The LLM sees a precise schema and can call your tools correctly.

Usage:
    uv run python examples/capabilities/tools/01_typed_tools.py
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import logging
from typing import Literal

from pydantic import BaseModel, Field

from dedalus_mcp import MCPServer, tool


for name in ("mcp", "httpx", "uvicorn"):
    logging.getLogger(name).setLevel(logging.WARNING)

server = MCPServer("typed-tools")


# Basic types
@tool(description="Add two numbers")
def add(a: int, b: int) -> int:
    return a + b


# Optional parameters with defaults
@tool(description="Greet someone")
def greet(name: str, formal: bool = False, times: int = 1) -> str:
    greeting = f"Good day, {name}." if formal else f"Hey {name}!"
    return " ".join([greeting] * times)


# Enum constraints
class Priority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@tool(description="Create a task with priority")
def create_task(title: str, priority: Priority = Priority.MEDIUM) -> dict:
    return {"title": title, "priority": priority.value, "created": datetime.now().isoformat()}


# Literal types for constrained strings
@tool(description="Set log level")
def set_log_level(level: Literal["debug", "info", "warning", "error"]) -> str:
    return f"Log level set to {level}"


# Pydantic models for complex input
class Address(BaseModel):
    street: str
    city: str
    country: str = "USA"


class Person(BaseModel):
    name: str
    age: int = Field(ge=0, le=150, description="Age in years")
    email: str | None = None
    address: Address | None = None


@tool(description="Register a person")
def register_person(person: Person) -> dict:
    return {"registered": True, "person": person.model_dump(), "timestamp": datetime.now().isoformat()}


# Dataclass output (auto-serialized)
@dataclass
class SearchResult:
    query: str
    results: list[str]
    total: int


@tool(description="Search with typed output")
def search(query: str, limit: int = 10) -> SearchResult:
    # Simulated search
    results = [f"Result {i} for '{query}'" for i in range(min(limit, 3))]
    return SearchResult(query=query, results=results, total=len(results))


server.collect(add, greet, create_task, set_log_level, register_person, search)

if __name__ == "__main__":
    print("Typed tools server: http://127.0.0.1:8000/mcp")
    print("\nTools with type inference:")
    print("  add(a: int, b: int) -> int")
    print("  greet(name: str, formal: bool = False, times: int = 1) -> str")
    print("  create_task(title: str, priority: Priority = MEDIUM) -> dict")
    print("  set_log_level(level: 'debug'|'info'|'warning'|'error') -> str")
    print("  register_person(person: Person) -> dict")
    print("  search(query: str, limit: int = 10) -> SearchResult")
    asyncio.run(server.serve())
