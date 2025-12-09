# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Dedalus MCP CLI utilities for local development and packaging checks."""

from __future__ import annotations

import argparse
import sys
from importlib import metadata
from pathlib import Path


def _installed_version() -> str:
    try:
        return metadata.version("dedalus_mcp")
    except metadata.PackageNotFoundError:
        return "0.0.0+local"


def _check_installation(package_root: Path) -> list[str]:
    issues: list[str] = []
    if not (package_root / "py.typed").exists():
        issues.append("py.typed typing marker is missing; type checkers will treat the package as untyped")
    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="dedalus_mcp",
        description="Dedalus MCP utilities for local development and packaging checks.",
    )
    subcommands = parser.add_subparsers(dest="command")

    subcommands.add_parser("version", help="Show the installed dedalus_mcp package version")
    subcommands.add_parser("doctor", help="Validate that the installation shipped required assets")

    args = parser.parse_args(argv)

    if args.command == "version":
        print(_installed_version())
        return 0

    if args.command == "doctor":
        package_root = Path(__file__).resolve().parent
        issues = _check_installation(package_root)
        if issues:
            for issue in issues:
                print(f"ERROR: {issue}", file=sys.stderr)
            return 1
        print("ok")
        return 0

    parser.print_help()
    return 0


__all__ = ["main"]


if __name__ == "__main__":
    raise SystemExit(main())
