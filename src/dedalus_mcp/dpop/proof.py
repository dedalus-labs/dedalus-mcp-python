# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""DPoP proof generation (client-side) per RFC 9449.

This module provides:
- generate_dpop_proof(): Create DPoP proof JWTs
- DPoPAuth: HTTPX auth handler for automatic header injection
- BearerAuth: Simple bearer token auth (fallback)

A DPoP proof is a JWT that demonstrates possession of a private key.
It contains:
- Header: typ="dpop+jwt", alg="ES256", jwk={public key}
- Payload: jti, htm, htu, iat, and optionally ath and nonce

References:
    RFC 9449 Section 4.2: DPoP Proof JWT Syntax
    RFC 9449 Section 7.1: The DPoP Authentication Scheme
"""

from __future__ import annotations

import time
import uuid
from typing import TYPE_CHECKING, Any, Generator
from urllib.parse import urlparse

if TYPE_CHECKING:
    from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePrivateKey

import httpx

from dedalus_mcp.dpop.thumbprint import b64url_encode, compute_access_token_hash, compute_jwk_thumbprint


def generate_dpop_proof(
    private_key: "EllipticCurvePrivateKey",
    method: str,
    url: str,
    access_token: str | None = None,
    nonce: str | None = None,
) -> str:
    """Generate a DPoP proof JWT per RFC 9449.

    Creates a fresh DPoP proof for a single HTTP request. Each proof contains:
    - Unique jti (JWT ID) for replay prevention
    - htm (HTTP method)
    - htu (HTTP target URI without query/fragment)
    - iat (issued-at timestamp)
    - ath (access token hash, if token provided) - required for resource server calls
    - nonce (if server requires it)

    Args:
        private_key: EC private key (P-256/ES256) for signing
        method: HTTP method (e.g., "GET", "POST")
        url: Full HTTP URL (query/fragment stripped per RFC 9449 Section 4.2)
        access_token: Optional access token to bind via ath claim.
                     MUST be provided when calling resource servers (RFC 9449 Section 7).
        nonce: Optional server-provided nonce (RFC 9449 Section 8)

    Returns:
        DPoP proof JWT string

    Example:
        >>> # For token endpoint (no access token yet)
        >>> proof = generate_dpop_proof(key, "POST", "https://as.example.com/token")
        >>>
        >>> # For resource server (with access token)
        >>> proof = generate_dpop_proof(
        ...     key, "POST", "https://mcp.example.com/messages",
        ...     access_token="eyJ..."
        ... )
    """
    import jwt

    # Extract public key as JWK for header
    public_key = private_key.public_key()
    public_numbers = public_key.public_numbers()

    coord_size = 32  # P-256 = 256 bits = 32 bytes
    x = b64url_encode(public_numbers.x.to_bytes(coord_size, byteorder="big"))
    y = b64url_encode(public_numbers.y.to_bytes(coord_size, byteorder="big"))

    jwk = {"kty": "EC", "crv": "P-256", "x": x, "y": y}

    # Header per RFC 9449 Section 4.2
    header = {"typ": "dpop+jwt", "alg": "ES256", "jwk": jwk}

    # Strip query and fragment from URL per RFC 9449 Section 4.2
    parsed = urlparse(url)
    htu = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    if not parsed.path:
        htu += "/"

    # Payload per RFC 9449 Section 4.2
    payload: dict[str, Any] = {
        "jti": str(uuid.uuid4()),
        "htm": method.upper(),
        "htu": htu,
        "iat": int(time.time()),
    }

    # RFC 9449 Section 7: ath MUST be present when sending to resource server
    if access_token is not None:
        payload["ath"] = compute_access_token_hash(access_token)

    # RFC 9449 Section 8: nonce when server requires it
    if nonce is not None:
        payload["nonce"] = nonce

    return jwt.encode(payload, private_key, algorithm="ES256", headers=header)


class DPoPAuth(httpx.Auth):
    """HTTPX auth handler for DPoP-bound tokens.

    Implements the httpx.Auth interface to automatically inject DPoP
    authorization headers on every request. Generates a fresh DPoP proof
    for each request as required by RFC 9449.

    The authorization flow:
    1. For each request, generate a new DPoP proof JWT
    2. Add `Authorization: DPoP {access_token}` header
    3. Add `DPoP: {proof_jwt}` header

    Attributes:
        access_token: The OAuth 2.1 access token
        dpop_key: EC private key (P-256) for signing proofs
        nonce: Optional server-provided nonce for replay prevention

    Example:
        >>> from dedalus_mcp.dpop import generate_dpop_keypair, DPoPAuth
        >>>
        >>> private_key, _ = generate_dpop_keypair()
        >>> auth = DPoPAuth(access_token="eyJ...", dpop_key=private_key)
        >>>
        >>> async with httpx.AsyncClient() as client:
        ...     response = await client.post(url, auth=auth, json=data)

    Notes:
        - The access token should be obtained from the authorization server
          with DPoP binding (cnf.jkt claim matching your key's thumbprint)
        - The same key used during token request MUST be used here
        - If the server returns a DPoP-Nonce header, update via set_nonce()
    """

    requires_response_body = False

    def __init__(
        self,
        access_token: str,
        dpop_key: "EllipticCurvePrivateKey",
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
        public_key = self._dpop_key.public_key()
        public_numbers = public_key.public_numbers()
        coord_size = 32
        jwk = {
            "kty": "EC",
            "crv": "P-256",
            "x": b64url_encode(public_numbers.x.to_bytes(coord_size, byteorder="big")),
            "y": b64url_encode(public_numbers.y.to_bytes(coord_size, byteorder="big")),
        }
        return compute_jwk_thumbprint(jwk)

    def set_nonce(self, nonce: str | None) -> None:
        """Update the DPoP nonce (e.g., from DPoP-Nonce response header).

        Per RFC 9449 Section 8, servers may require nonces for additional
        replay protection. When a server returns a DPoP-Nonce header in a 401
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

        Called by httpx for each request. Generates a fresh DPoP proof
        containing the request's method and URL.
        """
        # Generate fresh DPoP proof for this specific request
        proof = generate_dpop_proof(
            private_key=self._dpop_key,
            method=request.method,
            url=str(request.url),
            access_token=self._access_token,
            nonce=self._nonce,
        )

        # RFC 9449 Section 7.1: use "DPoP" scheme, not "Bearer"
        request.headers["Authorization"] = f"DPoP {self._access_token}"
        request.headers["DPoP"] = proof

        yield request


class BearerAuth(httpx.Auth):
    """Simple bearer token auth handler.

    For servers that don't require DPoP, this provides standard
    OAuth 2.0 Bearer token authentication.

    Example:
        >>> auth = BearerAuth(access_token="eyJ...")
        >>> async with httpx.AsyncClient() as client:
        ...     response = await client.get(url, auth=auth)
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
    "generate_dpop_proof",
    "DPoPAuth",
    "BearerAuth",
]
