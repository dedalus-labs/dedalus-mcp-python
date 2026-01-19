# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""License header checker and fixer for Python files.

Ensures all Python source files have the correct SPDX license header.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# MIT SPDX license header
MIT_LICENSE = """# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT"""

# Default configuration
DEFAULT_CONFIG = {
    "license_mapping": {"mit": {"dirs": ["src", "tests", "examples", ".github/scripts"]}},
    "exclude_patterns": [
        "**/venv/**",
        "**/.venv/**",
        "**/__pycache__/**",
        "**/build/**",
        "**/dist/**",
        "**/*.egg-info/**",
        "**/node_modules/**",
        "**/.git/**",
        "**/.pytest_cache/**",
        "**/.mypy_cache/**",
        "**/migrations/**",
        "**/htmlcov/**",
        "**/.coverage/**",
        "**/references/**",
        "**/internals/**",
    ],
    "exclude_files": ["__init__.py"],
    "remove_shebangs": True,
}


def load_config() -> dict:
    """Load configuration from file or use defaults."""
    config_path = Path(".github/license-header-config.json")
    if config_path.exists():
        with open(config_path) as f:
            user_config = json.load(f)
            config = DEFAULT_CONFIG.copy()
            if "license_mapping" in user_config:
                config["license_mapping"].update(user_config["license_mapping"])
            if "exclude_patterns" in user_config:
                config["exclude_patterns"] = user_config["exclude_patterns"]
            if "exclude_files" in user_config:
                config["exclude_files"] = user_config["exclude_files"]
            if "remove_shebangs" in user_config:
                config["remove_shebangs"] = user_config["remove_shebangs"]
            return config
    return DEFAULT_CONFIG


def get_license_header(license_type: str) -> str:
    """Get the license header for a given type."""
    if license_type == "mit":
        return MIT_LICENSE
    return MIT_LICENSE  # Default to MIT


def should_skip_file(file_path: Path, config: dict) -> bool:
    """Check if a file should be skipped based on configuration."""
    for pattern in config.get("exclude_patterns", []):
        if "**" in pattern:
            if file_path.match(pattern.replace("**/", "*/")):
                return True
        elif file_path.match(pattern):
            return True

    if file_path.name in config.get("exclude_files", []):
        return True

    return False


def find_python_files(config: dict) -> list[tuple[Path, str, str]]:
    """Find all Python files and their corresponding license types."""
    python_files = []
    seen_files: set[Path] = set()

    for license_type, license_config in config["license_mapping"].items():
        for include_dir in license_config.get("dirs", []):
            dir_path = Path(include_dir)
            if not dir_path.exists():
                print(f"Warning: Directory {include_dir} does not exist, skipping...")
                continue

            for file_path in dir_path.rglob("*.py"):
                if file_path not in seen_files and not should_skip_file(file_path, config):
                    seen_files.add(file_path)
                    license_header = get_license_header(license_type)
                    python_files.append((file_path, license_type, license_header))

    return sorted(python_files, key=lambda x: x[0])


def check_license_header(file_path: Path, expected_header: str) -> bool:
    """Check if a file has the correct license header."""
    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        # Remove any shebang line for checking
        if content.startswith("#!"):
            first_newline = content.find("\n")
            if first_newline != -1:
                content = content[first_newline + 1 :].lstrip()

        expected = expected_header.replace("\r\n", "\n").strip()
        return content.strip().startswith(expected)

    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return False


def fix_license_header(file_path: Path, expected_header: str, remove_shebang: bool = True) -> bool:
    """Fix the license header in a file."""
    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        original_content = content

        # Remove shebang if present and configured
        if remove_shebang and content.startswith("#!"):
            first_newline = content.find("\n")
            if first_newline != -1:
                content = content[first_newline + 1 :]
            else:
                content = ""

        # Remove any existing license headers
        license_patterns = [
            r"^# Copyright \(c\) \d+ .+\n# SPDX-License-Identifier: .+\n\n?",
            r"^# =+\n(?:# .+\n)*# =+\n\n?",
        ]

        for pattern in license_patterns:
            while True:
                content = content.lstrip()
                match = re.match(pattern, content, re.MULTILINE)
                if match:
                    content = content[match.end() :]
                else:
                    break

        # Add the correct license header
        content = content.lstrip()
        if content:
            new_content = expected_header + "\n\n" + content
        else:
            new_content = expected_header + "\n"

        if new_content != original_content:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)

        return True

    except Exception as e:
        print(f"Error fixing {file_path}: {e}")
        return False


def main() -> int:
    """Main function."""
    parser = argparse.ArgumentParser(description="Check and fix license headers in Python files")
    parser.add_argument("--check", action="store_true", help="Check files only (exit with error if missing)")
    parser.add_argument("--fix", action="store_true", help="Fix missing or incorrect headers")
    parser.add_argument("--verbose", action="store_true", help="Show all files being checked")

    args = parser.parse_args()

    if not args.check and not args.fix:
        parser.error("Please specify either --check or --fix")

    config = load_config()
    python_files = find_python_files(config)

    if not python_files:
        print("No Python files found in configured directories.")
        return 0

    print(f"Found {len(python_files)} Python files to check")

    incorrect_headers = []
    fixed_files = []

    for file_path, license_type, expected_header in python_files:
        has_correct_header = check_license_header(file_path, expected_header)

        if args.verbose or not has_correct_header:
            status = "✓" if has_correct_header else "✗"
            print(f"{status} {file_path} [{license_type}]")

        if not has_correct_header:
            incorrect_headers.append((file_path, license_type))

            if args.fix:
                if fix_license_header(file_path, expected_header, config.get("remove_shebangs", True)):
                    fixed_files.append(file_path)
                    print(f"  → Fixed {file_path}")
                else:
                    print(f"  → Failed to fix {file_path}")

    if incorrect_headers:
        print(f"\n{len(incorrect_headers)} files have incorrect license headers")

        if args.fix:
            print(f"{len(fixed_files)} files were fixed")
            if len(fixed_files) < len(incorrect_headers):
                print(f"{len(incorrect_headers) - len(fixed_files)} files could not be fixed")
                return 1
        else:
            print("\nRun with --fix to automatically fix headers")
            return 1
    else:
        print("\nAll files have correct license headers ✓")

    return 0


if __name__ == "__main__":
    sys.exit(main())
