# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Client-side authentication for MCP servers.

This module provides authentication handlers for connecting to protected
MCP servers. The primary class is `DPoPAuth`, which implements RFC 9449
DPoP (Demonstrating Proof of Possession) for sender-constrained tokens.

Example:
    >>> from dedalus_mcp.client import MCPClient
    >>> from dedalus_mcp.client.auth import DPoPAuth
    >>>
    >>> # Create auth handler with your access token and DPoP key
    >>> auth = DPoPAuth(access_token="eyJ...", dpop_key=private_key)
    >>>
    >>> # Connect with DPoP auth
    >>> client = await MCPClient.connect("https://mcp.example.com/mcp", auth=auth)
    >>> tools = await client.list_tools()
    >>> await client.close()

The DPoP proof is generated fresh for each request, as required by RFC 9449.
The proof binds the token to the specific HTTP method and URL being requested.

References:
    RFC 9449: OAuth 2.0 Demonstrating Proof of Possession (DPoP)
    /dcs/apps/openmcp_as/dpop/dpop.go (Go implementation)
    /dcs/apps/enclave/dispatch-gateway/src/handlers.rs (validation)
"""

from __future__ import annotations

import base64
import hashlib
import time
import uuid
from typing import TYPE_CHECKING, Any, Generator

if TYPE_CHECKING:
    from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePrivateKey

import httpx


def _b64url_encode(data: bytes) -> str:
    """Base64url encode without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _compute_ath(access_token: str) -> str:
    """Compute access token hash (ath claim) per RFC 9449 §6.1."""
    token_hash = hashlib.sha256(access_token.encode()).digest()
    return _b64url_encode(token_hash)


def _compute_jwk_thumbprint(public_key: Any) -> str:
    """Compute JWK thumbprint per RFC 7638.

    Args:
        public_key: EC public key (P-256)

    Returns:
        Base64url-encoded SHA-256 thumbprint
    """
    import json

    public_numbers = public_key.public_numbers()

    # RFC 7638 + RFC 7518 §6.2.1.3: coordinates must be padded to curve size
    coord_size = 32  # P-256 = 256 bits = 32 bytes

    x = _b64url_encode(public_numbers.x.to_bytes(coord_size, byteorder="big"))
    y = _b64url_encode(public_numbers.y.to_bytes(coord_size, byteorder="big"))

    # Lexicographically sorted (crv, kty, x, y)
    canonical = json.dumps({"crv": "P-256", "kty": "EC", "x": x, "y": y}, separators=(",", ":"), sort_keys=True)

    thumbprint = hashlib.sha256(canonical.encode()).digest()
    return _b64url_encode(thumbprint)


def generate_dpop_proof(
    dpop_key: EllipticCurvePrivateKey,
    method: str,
    url: str,
    access_token: str | None = None,
    nonce: str | None = None,
) -> str:
    """Generate a DPoP proof JWT per RFC 9449.

    This function creates a fresh DPoP proof for a single HTTP request.
    Each proof contains:
    - Unique jti (JWT ID) for replay prevention
    - htm (HTTP method)
    - htu (HTTP target URI without query/fragment)
    - iat (issued-at timestamp)
    - ath (access token hash, if token provided)
    - nonce (if server requires it)

    Args:
        dpop_key: EC private key (P-256/ES256) for signing
        method: HTTP method (e.g., "GET", "POST")
        url: Full HTTP URL (query/fragment stripped per RFC 9449 §4.2)
        access_token: Optional access token to bind via ath claim (RFC 9449 §7.1)
        nonce: Optional server-provided nonce (RFC 9449 §8)

    Returns:
        DPoP proof JWT string

    Example:
        >>> proof = generate_dpop_proof(key, "POST", "https://api.example.com/mcp")
    """
    import jwt

    # Extract public key as JWK for header
    public_key = dpop_key.public_key()
    public_numbers = public_key.public_numbers()

    coord_size = 32  # P-256
    x = _b64url_encode(public_numbers.x.to_bytes(coord_size, byteorder="big"))
    y = _b64url_encode(public_numbers.y.to_bytes(coord_size, byteorder="big"))

    jwk = {"kty": "EC", "crv": "P-256", "x": x, "y": y}

    # Header per RFC 9449 §4.2
    header = {"typ": "dpop+jwt", "alg": "ES256", "jwk": jwk}

    # Payload per RFC 9449 §4.2
    # Strip query and fragment from URL per §4.2
    from urllib.parse import urlparse

    parsed = urlparse(url)
    htu = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    if not parsed.path:
        htu += "/"

    payload: dict[str, Any] = {
        "jti": str(uuid.uuid4()),
        "htm": method.upper(),
        "htu": htu,
        "iat": int(time.time()),
    }

    # RFC 9449 §7.1: ath MUST be present when sending to resource server
    if access_token is not None:
        payload["ath"] = _compute_ath(access_token)

    # RFC 9449 §8: nonce when server requires it
    if nonce is not None:
        payload["nonce"] = nonce

    return jwt.encode(payload, dpop_key, algorithm="ES256", headers=header)


class DPoPAuth(httpx.Auth):
    """HTTPX auth handler for DPoP-bound tokens.

    This class implements the httpx.Auth interface to automatically inject
    DPoP authorization headers on every request. It generates a fresh DPoP
    proof for each request as required by RFC 9449.

    The authorization flow:
    1. For each request, generate a new DPoP proof JWT
    2. Add `Authorization: DPoP {access_token}` header
    3. Add `DPoP: {proof_jwt}` header

    Attributes:
        access_token: The OAuth 2.1 access token
        dpop_key: EC private key (P-256) for signing proofs
        nonce: Optional server-provided nonce for replay prevention

    Example:
        >>> from cryptography.hazmat.primitives.asymmetric import ec
        >>> from cryptography.hazmat.backends import default_backend
        >>>
        >>> # Generate or load your DPoP key
        >>> dpop_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
        >>>
        >>> # Create auth handler
        >>> auth = DPoPAuth(access_token="eyJ...", dpop_key=dpop_key)
        >>>
        >>> # Use with MCPClient
        >>> client = await MCPClient.connect(url, auth=auth)

    Notes:
        - The access token should be obtained from the authorization server
          with DPoP binding (cnf.jkt claim matching your key's thumbprint)
        - The same key used during token request MUST be used here
        - If the server returns a DPoP-Nonce header, update via `set_nonce()`
    """

    requires_response_body = False

    def __init__(
        self,
        access_token: str,
        dpop_key: EllipticCurvePrivateKey,
        nonce: str | None = None,
    ) -> None:
        """Initialize DPoP auth handler.

        Args:
            access_token: OAuth 2.1 access token (DPoP-bound)
            dpop_key: EC private key (P-256) for signing DPoP proofs.
                Must be the same key used during token request.
            nonce: Optional initial nonce from server
        """
        self._access_token = access_token
        self._dpop_key = dpop_key
        self._nonce = nonce

    @property
    def thumbprint(self) -> str:
        """JWK thumbprint of the DPoP key (for debugging/verification)."""
        return _compute_jwk_thumbprint(self._dpop_key.public_key())

    def set_nonce(self, nonce: str | None) -> None:
        """Update the DPoP nonce (e.g., from DPoP-Nonce response header).

        Per RFC 9449 §8, servers may require nonces for additional replay
        protection. When a server returns a DPoP-Nonce header in a 401
        response, call this method and retry the request.

        Args:
            nonce: New nonce value, or None to clear
        """
        self._nonce = nonce

    def set_access_token(self, token: str) -> None:
        """Update the access token (e.g., after refresh).

        Args:
            token: New access token
        """
        self._access_token = token

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        """Generate DPoP auth headers for the request.

        This is called by httpx for each request. We generate a fresh
        DPoP proof containing the request's method and URL.
        """
        # Generate fresh DPoP proof for this specific request
        proof = generate_dpop_proof(
            dpop_key=self._dpop_key,
            method=request.method,
            url=str(request.url),
            access_token=self._access_token,
            nonce=self._nonce,
        )

        # RFC 9449 §7.1: use "DPoP" scheme, not "Bearer"
        request.headers["Authorization"] = f"DPoP {self._access_token}"
        request.headers["DPoP"] = proof

        yield request


class BearerAuth(httpx.Auth):
    """Simple bearer token auth handler.

    For servers that don't require DPoP, this provides standard
    OAuth 2.0 Bearer token authentication.

    Example:
        >>> auth = BearerAuth(access_token="eyJ...")
        >>> client = await MCPClient.connect(url, auth=auth)
    """

    requires_response_body = False

    def __init__(self, access_token: str) -> None:
        """Initialize bearer auth handler.

        Args:
            access_token: OAuth 2.0/2.1 access token
        """
        self._access_token = access_token

    def set_access_token(self, token: str) -> None:
        """Update the access token (e.g., after refresh).

        Args:
            token: New access token
        """
        self._access_token = token

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        """Add Bearer authorization header."""
        request.headers["Authorization"] = f"Bearer {self._access_token}"
        yield request


__all__ = [
    "BearerAuth",
    "DPoPAuth",
    "generate_dpop_proof",
]

