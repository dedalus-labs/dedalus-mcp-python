# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Tests for docstring parameter extraction.

Validates that parameter descriptions are correctly parsed from
Google, NumPy, and Sphinx/reST style docstrings and injected into
tool input schemas for improved LLM discoverability.
"""

from __future__ import annotations

import pytest

from dedalus_mcp import MCPServer
from dedalus_mcp.tool import tool
from dedalus_mcp.utils.docstring import parse_docstring_params


# --- Unit tests for parse_docstring_params ---


def test_parse_google_style_docstring():
    """Google-style Args section is correctly parsed."""
    docstring = """
    Do something useful.

    Args:
        first: The first argument
        second: The second argument with
            multiple lines of description
        third: Third one

    Returns:
        Something useful

    """
    params = parse_docstring_params(docstring)

    assert params["first"] == "The first argument"
    assert "second argument" in params["second"]
    assert "multiple lines" in params["second"]
    assert params["third"] == "Third one"


def test_parse_google_style_with_types():
    """Google-style with inline type annotations."""
    docstring = """
    Function.

    Args:
        name (str): The name
        count (int, optional): The count. Defaults to 1.

    """
    params = parse_docstring_params(docstring)

    assert params["name"] == "The name"
    assert "The count" in params["count"]


def test_parse_numpy_style_docstring():
    """NumPy-style Parameters section is correctly parsed."""
    docstring = """
    Do something useful.

    Parameters
    ----------
    x : int
        The x coordinate
    y : float
        The y coordinate

    """
    params = parse_docstring_params(docstring)

    assert "x" in params
    assert "x coordinate" in params["x"]
    assert "y" in params
    assert "y coordinate" in params["y"]


def test_parse_sphinx_style_docstring():
    """Sphinx/reST-style :param: fields are correctly parsed."""
    docstring = """
    Do something useful.

    :param name: The name to use
    :type name: str
    :param count: How many times
    :returns: Result string

    """
    params = parse_docstring_params(docstring)

    assert params["name"] == "The name to use"
    assert params["count"] == "How many times"


def test_parse_empty_docstring():
    """Empty or None docstring returns empty dict."""
    assert parse_docstring_params(None) == {}
    assert parse_docstring_params("") == {}
    assert parse_docstring_params("   ") == {}


def test_parse_docstring_no_params_section():
    """Docstring without params section returns empty dict."""
    docstring = """
    Just a description.

    Returns:
        Something

    """
    assert parse_docstring_params(docstring) == {}


# --- Integration tests with MCPServer ---


@pytest.mark.asyncio
async def test_google_docstring_params_in_schema():
    """Parameter descriptions from Google-style docstrings appear in inputSchema."""
    server = MCPServer("docstring-test")

    with server.binding():

        @tool(description="Get user by username")
        def get_user(username: str, include_details: bool = False) -> dict:
            """Fetch a user from the database.

            Args:
                username: The user's unique identifier (without @ prefix)
                include_details: Whether to include extended profile information

            Returns:
                User data dictionary

            """
            return {"username": username}

    schema = server.tools.definitions["get_user"].inputSchema
    props = schema["properties"]

    assert "username" in props
    assert props["username"].get("description") == "The user's unique identifier (without @ prefix)"
    assert "include_details" in props
    assert props["include_details"].get("description") == "Whether to include extended profile information"


@pytest.mark.asyncio
async def test_multiline_param_description():
    """Multi-line parameter descriptions are properly concatenated."""
    server = MCPServer("multiline-test")

    with server.binding():

        @tool()
        def search(query: str, filters: dict | None = None) -> list:
            """Search for items.

            Args:
                query: The search query string. Supports advanced operators
                    like AND, OR, and quoted phrases for exact matches.
                filters: Optional dictionary of filter criteria.

            """
            return []

    schema = server.tools.definitions["search"].inputSchema
    props = schema["properties"]

    desc = props["query"].get("description", "")
    assert "search query string" in desc
    assert "advanced operators" in desc


@pytest.mark.asyncio
async def test_no_docstring_uses_fallback():
    """Tools without docstrings get generic parameter descriptions."""
    server = MCPServer("no-docstring")

    with server.binding():

        @tool(description="Add numbers")
        def add(a: int, b: int) -> int:
            return a + b

    schema = server.tools.definitions["add"].inputSchema
    props = schema["properties"]

    assert "a" in props
    assert "b" in props
    assert props["a"].get("description") is not None
    assert props["b"].get("description") is not None


@pytest.mark.asyncio
async def test_partial_docstring_params():
    """Docstring with some but not all params documented."""
    server = MCPServer("partial-docstring")

    with server.binding():

        @tool()
        def mixed(documented: str, undocumented: int) -> str:
            """Do something.

            Args:
                documented: This parameter has documentation

            """
            return documented

    schema = server.tools.definitions["mixed"].inputSchema
    props = schema["properties"]

    assert props["documented"].get("description") == "This parameter has documentation"
    assert props["undocumented"].get("description") is not None


@pytest.mark.asyncio
async def test_async_tool_docstring_extraction():
    """Async tools also get docstring parameter extraction."""
    server = MCPServer("async-docstring")

    with server.binding():

        @tool()
        async def fetch_data(url: str, timeout: int = 30) -> dict:
            """Fetch data from a URL.

            Args:
                url: The URL to fetch from
                timeout: Request timeout in seconds

            """
            return {"url": url}

    schema = server.tools.definitions["fetch_data"].inputSchema
    props = schema["properties"]

    assert props["url"].get("description") == "The URL to fetch from"
    assert props["timeout"].get("description") == "Request timeout in seconds"


@pytest.mark.asyncio
async def test_explicit_input_schema_takes_precedence():
    """Explicit input_schema parameter overrides docstring extraction."""
    server = MCPServer("explicit-schema")

    explicit_schema = {
        "type": "object",
        "properties": {"value": {"type": "string", "description": "Explicit description"}},
        "required": ["value"],
    }

    with server.binding():

        @tool(input_schema=explicit_schema)
        def with_schema(value: str) -> str:
            """Tool with explicit schema.

            Args:
                value: This should be ignored

            """
            return value

    schema = server.tools.definitions["with_schema"].inputSchema
    assert schema["properties"]["value"]["description"] == "Explicit description"


@pytest.mark.asyncio
async def test_numpy_docstring_params_in_schema():
    """NumPy-style docstrings are supported in tool schemas."""
    server = MCPServer("numpy-docstring")

    with server.binding():

        @tool()
        def numpy_style(array: list, axis: int = 0) -> float:
            """Compute the mean of an array.

            Parameters
            ----------
            array : list
                Input array to compute mean of
            axis : int, optional
                Axis along which to compute, by default 0

            """
            return sum(array) / len(array) if array else 0.0

    schema = server.tools.definitions["numpy_style"].inputSchema
    props = schema["properties"]

    assert "Input array" in props["array"].get("description", "")
    assert "Axis along which" in props["axis"].get("description", "")


@pytest.mark.asyncio
async def test_sphinx_docstring_params_in_schema():
    """Sphinx/reST-style docstrings are supported in tool schemas."""
    server = MCPServer("sphinx-docstring")

    with server.binding():

        @tool()
        def sphinx_style(path: str, mode: str = "r") -> str:
            """Read a file.

            :param path: Path to the file to read
            :param mode: File open mode
            :returns: File contents

            """
            return ""

    schema = server.tools.definitions["sphinx_style"].inputSchema
    props = schema["properties"]

    assert "Path to the file" in props["path"].get("description", "")
    assert "File open mode" in props["mode"].get("description", "")
