# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""OAuth discovery (RFC 9728, RFC 8414).

This module implements the discovery flow for MCP OAuth:
1. Probe resource for 401 with WWW-Authenticate header
2. Fetch Protected Resource Metadata (PRM) per RFC 9728
3. Fetch Authorization Server Metadata per RFC 8414
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx

from .models import (
    AuthorizationServerMetadata,
    ResourceMetadata,
    parse_www_authenticate,
)


class DiscoveryError(Exception):
    """Error during OAuth discovery."""


@dataclass
class DiscoveryResult:
    """Result of OAuth discovery."""

    resource_metadata: ResourceMetadata
    authorization_server_metadata: AuthorizationServerMetadata


def build_resource_metadata_url(base_url: str, resource_metadata_path: str) -> str:
    """Build the full URL for Protected Resource Metadata.

    Args:
        base_url: The base resource URL (e.g., https://mcp.example.com/mcp)
        resource_metadata_path: The path from WWW-Authenticate header

    Returns:
        Full URL to fetch PRM from.
    """
    # If it's already a full URL, return as-is
    if resource_metadata_path.startswith("http://") or resource_metadata_path.startswith("https://"):
        return resource_metadata_path

    # If it starts with /, it's absolute path from origin
    if resource_metadata_path.startswith("/"):
        parsed = urlparse(base_url)
        return f"{parsed.scheme}://{parsed.netloc}{resource_metadata_path}"

    # Otherwise, relative path - resolve against base URL
    return urljoin(base_url, resource_metadata_path)


def build_authorization_server_metadata_url(issuer: str) -> str:
    """Build the well-known URL for Authorization Server Metadata.

    Per RFC 8414, if issuer has a path, insert .well-known between
    the origin and the path.

    Args:
        issuer: The authorization server issuer URL.

    Returns:
        The .well-known URL for AS metadata.
    """
    issuer = issuer.rstrip("/")
    parsed = urlparse(issuer)

    # If there's a path component, insert .well-known before it
    if parsed.path and parsed.path != "/":
        path = parsed.path.lstrip("/")
        return f"{parsed.scheme}://{parsed.netloc}/.well-known/oauth-authorization-server/{path}"

    return f"{issuer}/.well-known/oauth-authorization-server"


async def fetch_resource_metadata(client: httpx.AsyncClient, url: str) -> ResourceMetadata:
    """Fetch Protected Resource Metadata (RFC 9728).

    Args:
        client: HTTP client to use for the request.
        url: Full URL to the PRM endpoint.

    Returns:
        Parsed ResourceMetadata.

    Raises:
        DiscoveryError: If the fetch fails or response is invalid.
    """
    response = await client.get(url)

    if response.status_code != 200:
        raise DiscoveryError(f"Failed to fetch resource metadata: {response.status_code}")

    try:
        data = response.json()
    except Exception as e:
        raise DiscoveryError(f"Invalid JSON in resource metadata response: {e}") from e

    return ResourceMetadata.from_dict(data)


async def fetch_authorization_server_metadata(client: httpx.AsyncClient, issuer: str) -> AuthorizationServerMetadata:
    """Fetch Authorization Server Metadata (RFC 8414).

    Args:
        client: HTTP client to use for the request.
        issuer: The authorization server issuer URL.

    Returns:
        Parsed AuthorizationServerMetadata.

    Raises:
        DiscoveryError: If the fetch fails or response is invalid.
    """
    url = build_authorization_server_metadata_url(issuer)
    response = await client.get(url)

    if response.status_code != 200:
        raise DiscoveryError(f"Failed to fetch AS metadata: {response.status_code}")

    try:
        data = response.json()
    except Exception as e:
        raise DiscoveryError(f"Invalid JSON in AS metadata response: {e}") from e

    return AuthorizationServerMetadata.from_dict(data)


async def discover_authorization_server(
    client: httpx.AsyncClient,
    resource_url: str,
) -> DiscoveryResult:
    """Perform full OAuth discovery flow.

    This implements the MCP spec-compliant discovery:
    1. Probe the resource URL, expecting 401
    2. Parse WWW-Authenticate header for resource_metadata path
    3. Fetch Protected Resource Metadata
    4. Fetch Authorization Server Metadata

    Args:
        client: HTTP client to use for requests.
        resource_url: URL of the protected resource (e.g., MCP endpoint).

    Returns:
        DiscoveryResult with both resource and AS metadata.

    Raises:
        DiscoveryError: If discovery fails at any step.
    """
    # Step 1: Probe resource for 401
    response = await client.get(resource_url)

    if response.status_code != 401:
        raise DiscoveryError(f"Resource is not protected (got {response.status_code}, expected 401)")

    # Step 2: Parse WWW-Authenticate header
    www_auth = response.headers.get("WWW-Authenticate")
    if not www_auth:
        raise DiscoveryError("401 response missing WWW-Authenticate header")

    challenge = parse_www_authenticate(www_auth)
    if not challenge.resource_metadata:
        raise DiscoveryError("WWW-Authenticate header missing resource_metadata parameter")

    # Step 3: Fetch Protected Resource Metadata
    prm_url = build_resource_metadata_url(resource_url, challenge.resource_metadata)
    resource_metadata = await fetch_resource_metadata(client, prm_url)

    # Step 4: Fetch AS Metadata (use first/primary AS)
    as_url = resource_metadata.primary_authorization_server
    authorization_server_metadata = await fetch_authorization_server_metadata(client, as_url)

    return DiscoveryResult(
        resource_metadata=resource_metadata,
        authorization_server_metadata=authorization_server_metadata,
    )
