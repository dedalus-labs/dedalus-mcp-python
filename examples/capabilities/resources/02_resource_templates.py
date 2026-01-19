# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Resource templates — parameterized resources.

Templates let clients request resources with parameters in the URI.
Think REST-style paths: users/{id}, files/{path}, etc.

Usage:
    uv run python examples/capabilities/resources/02_resource_templates.py
"""

import asyncio
import logging
from datetime import datetime, timedelta

from dedalus_mcp import MCPServer, resource_template

for name in ("mcp", "httpx", "uvicorn"):
    logging.getLogger(name).setLevel(logging.WARNING)

server = MCPServer("resource-templates")

# Simulated data
USERS = {
    "1": {"id": 1, "name": "Alice", "email": "alice@example.com", "role": "admin"},
    "2": {"id": 2, "name": "Bob", "email": "bob@example.com", "role": "user"},
    "3": {"id": 3, "name": "Charlie", "email": "charlie@example.com", "role": "user"},
}

POSTS = {
    "1": {"id": 1, "author_id": 1, "title": "Hello World", "body": "First post!"},
    "2": {"id": 2, "author_id": 1, "title": "MCP Guide", "body": "Learn MCP..."},
    "3": {"id": 3, "author_id": 2, "title": "Python Tips", "body": "Type hints..."},
}


@resource_template(
    uri_template="users://{user_id}",
    name="User by ID",
    description="Fetch a user by their ID",
    mime_type="application/json",
)
def get_user(user_id: str) -> dict:
    user = USERS.get(user_id)
    if user is None:
        return {"error": f"User {user_id} not found"}
    return user


@resource_template(
    uri_template="users://{user_id}/posts",
    name="User's Posts",
    description="Get all posts by a user",
    mime_type="application/json",
)
def get_user_posts(user_id: str) -> dict:
    user_posts = [p for p in POSTS.values() if str(p["author_id"]) == user_id]
    return {"user_id": user_id, "posts": user_posts, "count": len(user_posts)}


@resource_template(
    uri_template="posts://{post_id}",
    name="Post by ID",
    description="Fetch a post by its ID",
    mime_type="application/json",
)
def get_post(post_id: str) -> dict:
    post = POSTS.get(post_id)
    if post is None:
        return {"error": f"Post {post_id} not found"}
    # Enrich with author info
    author = USERS.get(str(post["author_id"]))
    return {**post, "author": author}


@resource_template(
    uri_template="logs://{date}",
    name="Logs by Date",
    description="Get logs for a specific date (YYYY-MM-DD)",
    mime_type="text/plain",
)
def get_logs(date: str) -> str:
    # Simulated log entries
    return f"""=== Logs for {date} ===
10:00:00 INFO  Server started
10:00:01 INFO  Connected to database
10:15:30 DEBUG Processing request #1
10:15:31 INFO  Request #1 completed (200ms)
11:30:00 WARN  High memory usage detected
12:00:00 INFO  Scheduled backup started
12:05:00 INFO  Backup completed successfully
"""


@resource_template(
    uri_template="metrics://{service}/{period}",
    name="Service Metrics",
    description="Get metrics for a service over a time period",
    mime_type="application/json",
)
def get_metrics(service: str, period: str) -> dict:
    # Simulated metrics
    now = datetime.now()
    return {
        "service": service,
        "period": period,
        "timestamp": now.isoformat(),
        "metrics": {
            "requests": 12500,
            "errors": 23,
            "latency_p50_ms": 45,
            "latency_p99_ms": 230,
            "cpu_percent": 35.2,
            "memory_mb": 512,
        },
    }


server.collect(get_user, get_user_posts, get_post, get_logs, get_metrics)

if __name__ == "__main__":
    print("Resource templates server: http://127.0.0.1:8000/mcp")
    print("\nTemplates (try these URIs):")
    print("  users://1                  - Get user 1 (Alice)")
    print("  users://1/posts            - Get Alice's posts")
    print("  posts://2                  - Get post 2 with author")
    print("  logs://2024-01-15          - Get logs for date")
    print("  metrics://api/24h          - Get API metrics for 24h")
    asyncio.run(server.serve())
