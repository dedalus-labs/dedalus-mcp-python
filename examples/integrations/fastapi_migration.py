# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Migrate FastAPI endpoints to MCP tools.

If you have existing FastAPI routes, you can expose them as MCP tools
with minimal changes. This example shows the pattern.

Requirements (not in pyproject.toml — install separately):
    uv pip install fastapi

Usage:
    uv run python examples/integrations/fastapi_migration.py
"""

import asyncio
from datetime import datetime
import logging
from typing import Literal

from pydantic import BaseModel, Field

from dedalus_mcp import MCPServer, tool


for name in ("mcp", "httpx", "uvicorn"):
    logging.getLogger(name).setLevel(logging.WARNING)


# ============================================================================
# Your existing FastAPI models (unchanged)
# ============================================================================


class UserCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")
    role: Literal["user", "admin"] = "user"


class User(BaseModel):
    id: int
    name: str
    email: str
    role: str
    created_at: datetime


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    priority: Literal["low", "medium", "high"] = "medium"
    assignee_id: int | None = None


class Task(BaseModel):
    id: int
    title: str
    description: str | None
    priority: str
    status: str
    assignee_id: int | None
    created_at: datetime


# ============================================================================
# Your existing service layer (unchanged)
# ============================================================================

# Simulated database
_users: dict[int, User] = {}
_tasks: dict[int, Task] = {}
_next_user_id = 1
_next_task_id = 1


def create_user_service(data: UserCreate) -> User:
    global _next_user_id
    user = User(id=_next_user_id, **data.model_dump(), created_at=datetime.now())
    _users[user.id] = user
    _next_user_id += 1
    return user


def get_user_service(user_id: int) -> User | None:
    return _users.get(user_id)


def list_users_service() -> list[User]:
    return list(_users.values())


def create_task_service(data: TaskCreate) -> Task:
    global _next_task_id
    task = Task(id=_next_task_id, **data.model_dump(), status="todo", created_at=datetime.now())
    _tasks[task.id] = task
    _next_task_id += 1
    return task


def list_tasks_service(status: str | None = None) -> list[Task]:
    tasks = list(_tasks.values())
    if status:
        tasks = [t for t in tasks if t.status == status]
    return tasks


# ============================================================================
# FastAPI routes (commented out — shown for reference)
# ============================================================================

# from fastapi import FastAPI, HTTPException
# app = FastAPI()
#
# @app.post("/users", response_model=User)
# def create_user(data: UserCreate):
#     return create_user_service(data)
#
# @app.get("/users/{user_id}", response_model=User)
# def get_user(user_id: int):
#     user = get_user_service(user_id)
#     if not user:
#         raise HTTPException(404, "User not found")
#     return user
#
# @app.get("/users", response_model=list[User])
# def list_users():
#     return list_users_service()
#
# @app.post("/tasks", response_model=Task)
# def create_task(data: TaskCreate):
#     return create_task_service(data)
#
# @app.get("/tasks", response_model=list[Task])
# def list_tasks(status: str | None = None):
#     return list_tasks_service(status)


# ============================================================================
# MCP tools — wrap your service layer
# ============================================================================

server = MCPServer("fastapi-migration", instructions="Migrated from FastAPI endpoints")


@tool(description="Create a new user", tags={"users", "write"})
def create_user(data: UserCreate) -> User:
    """POST /users → MCP tool"""
    return create_user_service(data)


@tool(description="Get user by ID", tags={"users", "read"})
def get_user(user_id: int) -> User | dict:
    """GET /users/{id} → MCP tool"""
    user = get_user_service(user_id)
    if not user:
        return {"error": "User not found", "user_id": user_id}
    return user


@tool(description="List all users", tags={"users", "read"})
def list_users() -> list[User]:
    """GET /users → MCP tool"""
    return list_users_service()


@tool(description="Create a new task", tags={"tasks", "write"})
def create_task(data: TaskCreate) -> Task:
    """POST /tasks → MCP tool"""
    return create_task_service(data)


@tool(description="List tasks with optional status filter", tags={"tasks", "read"})
def list_tasks(status: Literal["todo", "in_progress", "done"] | None = None) -> list[Task]:
    """GET /tasks → MCP tool"""
    return list_tasks_service(status)


server.collect(create_user, get_user, list_users, create_task, list_tasks)

# ============================================================================
# Run both FastAPI and MCP (if FastAPI is available)
# ============================================================================


async def main() -> None:
    print("FastAPI → MCP Migration Example")
    print("=" * 40)
    print("\nMCP Server: http://127.0.0.1:8000/mcp")
    print("\nMigrated endpoints:")
    print("  POST /users      → create_user tool")
    print("  GET /users/{id}  → get_user tool")
    print("  GET /users       → list_users tool")
    print("  POST /tasks      → create_task tool")
    print("  GET /tasks       → list_tasks tool")
    print("\nYour Pydantic models work unchanged!")
    print("Your service layer works unchanged!")
    print("\nThe MCP tools just wrap your existing business logic.")

    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
