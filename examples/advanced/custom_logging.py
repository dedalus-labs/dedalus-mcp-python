# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Custom logging configuration for Dedalus MCP.

Demonstrates how to configure structured JSON logging using orjson and Pydantic
for production applications. Shows three patterns: JSON logging, custom colors,
and filtered handlers.

Pattern:
1. Use setup_logger() with json_serializer for structured logging
2. Subclass ColoredFormatter to customize color schemes
3. Subclass Dedalus MCPHandler to add filtering logic

When to use this pattern:
- Production environments requiring structured logs
- Custom color schemes for development ergonomics
- Filtered logging to reduce noise from verbose modules
- Integration with log aggregation systems (ELK, Splunk, Datadog)

Reference:
    - Logger utilities: src/dedalus_mcp/utils/logger.py
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, ClassVar, cast

from pydantic import BaseModel

from dedalus_mcp import MCPServer, tool
from dedalus_mcp.utils.logger import ColoredFormatter, Dedalus MCPHandler, get_logger, setup_logger

# Suppress SDK and server logs for cleaner demo output
for logger_name in ("mcp", "httpx", "uvicorn", "uvicorn.access", "uvicorn.error"):
    logging.getLogger(logger_name).setLevel(logging.CRITICAL)

try:
    import orjson  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    orjson = None


class LogEvent(BaseModel):
    """Structured log payload."""

    stage: str
    message: str
    severity: str


def _serialize(payload: dict[str, Any]) -> str:
    """Serialize payload using fastest available encoder."""
    if orjson is not None:
        encoded = orjson.dumps(payload, option=orjson.OPT_APPEND_NEWLINE)
        return cast("bytes", encoded).decode()
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


# Example 1: JSON logging for production
def configure_json_logging() -> None:
    """Configure structured JSON logging."""
    setup_logger(
        use_json=True,
        json_serializer=_serialize,
        payload_transformer=lambda p: {
            **p,
            "context": LogEvent(**p.get("context", {})).model_dump() if p.get("context") else None,
        },
        force=True,
    )


# Example 2: Custom color scheme
class PastelColors(ColoredFormatter):
    """Pastel color scheme for development."""

    LEVEL_COLORS: ClassVar[dict[str, str]] = {
        "DEBUG": "\033[38;5;117m",  # Light blue
        "INFO": "\033[38;5;156m",  # Light green
        "WARNING": "\033[38;5;222m",  # Light orange
        "ERROR": "\033[38;5;210m",  # Light red
        "CRITICAL": "\033[38;5;201m",  # Bright pink
    }


# Example 3: Filtered handler
class FilteredHandler(Dedalus MCPHandler):
    """Handler that filters out debug messages from specific modules."""

    def emit(self, record: logging.LogRecord) -> None:
        if record.levelno == logging.DEBUG and "noisy" in record.name:
            return
        super().emit(record)


async def main() -> None:
    """Run MCP server with custom JSON logging."""
    configure_json_logging()
    server = MCPServer("custom-logging")

    with server.binding():

        @tool()
        async def echo(message: str) -> str:
            event = LogEvent(stage="echo", message=message, severity="info")
            log = get_logger(__name__)
            log.info("tool-invoked", **event.model_dump())
            return message

    await server.serve_stdio(validate=False)


def demo_colors() -> None:
    """Show different color schemes."""
    print("\n=== Default Colors ===")
    setup_logger(level=logging.DEBUG, force=True)
    logger = get_logger("default")
    logger.debug("Debug: Cyan")
    logger.info("Info: Green")
    logger.warning("Warning: Yellow")
    logger.error("Error: Red")

    print("\n=== Pastel Colors ===")
    setup_logger(level=logging.DEBUG, force=True)
    root = logging.getLogger()
    for handler in root.handlers:
        handler.setFormatter(PastelColors(fmt="%(levelname)s %(message)s"))
    logger = get_logger("pastel")
    logger.debug("Debug: Light blue")
    logger.info("Info: Light green")
    logger.warning("Warning: Light orange")
    logger.error("Error: Light red")


if __name__ == "__main__":
    import sys

    if "--demo" in sys.argv:
        demo_colors()
    else:
        asyncio.run(main())
