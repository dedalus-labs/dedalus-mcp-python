# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Docstring parsing utilities for extracting parameter descriptions.

Supports Google, NumPy, and Sphinx/reST docstring styles.
"""

from __future__ import annotations

import re


__all__ = ["parse_docstring_params"]

# Maximum indentation for a parameter line (vs description continuation)
_MAX_PARAM_INDENT = 4


def parse_docstring_params(docstring: str | None) -> dict[str, str]:
    """Extract parameter descriptions from a docstring.

    Supports three common docstring formats:
    - Google style: Args: section with indented params
    - NumPy style: Parameters section with dashed underline
    - Sphinx/reST style: :param name: description

    Args:
        docstring: The docstring to parse, or None

    Returns:
        Dictionary mapping parameter names to their descriptions.
        Empty dict if no parameters found or docstring is empty.

    """
    if not docstring or not docstring.strip():
        return {}

    # Try each parser in order of most common usage
    result = _parse_google_style(docstring)
    if result:
        return result

    result = _parse_numpy_style(docstring)
    if result:
        return result

    result = _parse_sphinx_style(docstring)
    if result:
        return result

    return {}


def _parse_google_style(docstring: str) -> dict[str, str]:
    """Parse Google-style docstring Args section."""
    params: dict[str, str] = {}

    # Find Args: or Arguments: section
    args_match = re.search(r"(?:Args|Arguments):\s*\n", docstring, re.IGNORECASE)
    if not args_match:
        return params

    start = args_match.end()
    content = docstring[start:]

    # Find where Args section ends (next section or end)
    section_pattern = r"\n\s*(?:Returns|Raises|Yields|Examples?|Notes?|See Also|References|Warnings?|Attributes?):"
    end_match = re.search(section_pattern, content, re.IGNORECASE)
    if end_match:
        content = content[: end_match.start()]

    # Parse individual parameters
    lines = content.split("\n")
    current_param: str | None = None
    current_desc_lines: list[str] = []

    # Detect base indentation
    base_indent = 0
    for line in lines:
        stripped = line.lstrip()
        if stripped:
            base_indent = len(line) - len(stripped)
            break

    for line in lines:
        stripped = line.lstrip()
        if not stripped:
            continue

        line_indent = len(line) - len(stripped)

        # Check for new parameter: name (optional type): description
        param_match = re.match(r"(\w+)(?:\s*\([^)]*\))?\s*:\s*(.*)$", stripped)

        if param_match and line_indent <= base_indent + _MAX_PARAM_INDENT:
            if current_param is not None:
                params[current_param] = " ".join(current_desc_lines).strip()

            current_param = param_match.group(1)
            current_desc_lines = [param_match.group(2)] if param_match.group(2) else []

        elif current_param is not None and line_indent > base_indent:
            current_desc_lines.append(stripped)

    if current_param is not None:
        params[current_param] = " ".join(current_desc_lines).strip()

    return params


def _parse_numpy_style(docstring: str) -> dict[str, str]:
    """Parse NumPy-style docstring Parameters section."""
    params: dict[str, str] = {}

    # Find Parameters section with underline (handles varying whitespace)
    params_match = re.search(r"Parameters\s*\n\s*-+\s*\n", docstring, re.IGNORECASE)
    if not params_match:
        return params

    start = params_match.end()
    content = docstring[start:]

    # Find where section ends (another section header with underline)
    section_end = re.search(r"\n\s*[A-Z]\w+\s*\n\s*-+", content)
    if section_end:
        content = content[: section_end.start()]

    lines = content.split("\n")
    current_param: str | None = None
    current_desc_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # NumPy style: param : type on one line, description indented below
        param_match = re.match(r"^(\w+)\s*:\s*(.*)$", stripped)

        # Check if this looks like a parameter line (not heavily indented)
        raw_indent = len(line) - len(line.lstrip())

        if param_match and raw_indent <= _MAX_PARAM_INDENT:
            # Save previous param
            if current_param is not None:
                params[current_param] = " ".join(current_desc_lines).strip()

            current_param = param_match.group(1)
            current_desc_lines = []

        elif current_param is not None:
            # Description line (indented)
            current_desc_lines.append(stripped)

    # Save last param
    if current_param is not None:
        params[current_param] = " ".join(current_desc_lines).strip()

    return params


def _parse_sphinx_style(docstring: str) -> dict[str, str]:
    """Parse Sphinx/reST-style docstring :param: fields."""
    params: dict[str, str] = {}

    pattern = r":param\s+(\w+):\s*(.+?)(?=(?:\n\s*:|$))"
    matches = re.findall(pattern, docstring, re.DOTALL)

    for name, description in matches:
        desc = " ".join(line.strip() for line in description.split("\n"))
        params[name] = desc.strip()

    return params
