# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""JWK thumbprint and hash utilities per RFC 7638 and RFC 9449.

This module provides shared utilities used by both client and server:
- JWK thumbprint computation (RFC 7638)
- Access token hash for ath claim (RFC 9449 Section 6.1)
- Base64url encoding without padding

References:
    RFC 7638: JSON Web Key (JWK) Thumbprint
    RFC 9449 Section 6.1: JWK Thumbprint Confirmation Method
"""

from __future__ import annotations

import base64
import hashlib
import json
from typing import Any


def b64url_encode(data: bytes) -> str:
    """Base64url encode without padding per RFC 4648 Section 5.

    Args:
        data: Bytes to encode

    Returns:
        Base64url-encoded string without padding
    """
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(s: str) -> bytes:
    """Base64url decode with padding restoration.

    Args:
        s: Base64url-encoded string (with or without padding)

    Returns:
        Decoded bytes
    """
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


def compute_jwk_thumbprint(jwk: dict[str, Any]) -> str:
    """Compute JWK thumbprint per RFC 7638.

    The thumbprint is a SHA-256 hash of the canonical JSON representation
    of the required JWK members, base64url-encoded without padding.

    For EC keys (P-256, P-384, P-521), required members are: crv, kty, x, y
    For RSA keys, required members are: e, kty, n

    Args:
        jwk: JWK dictionary containing key parameters

    Returns:
        Base64url-encoded SHA-256 hash of canonical JWK representation

    Raises:
        ValueError: If key type is unsupported

    Example:
        >>> jwk = {"kty": "EC", "crv": "P-256", "x": "...", "y": "..."}
        >>> thumbprint = compute_jwk_thumbprint(jwk)
        >>> # thumbprint is 43 characters (256 bits / 6 bits per char)
    """
    kty = jwk.get("kty")

    if kty == "EC":
        # EC key: required members are crv, kty, x, y (alphabetically sorted)
        canonical_dict = {
            "crv": jwk["crv"],
            "kty": jwk["kty"],
            "x": jwk["x"],
            "y": jwk["y"],
        }
    elif kty == "RSA":
        # RSA key: required members are e, kty, n (alphabetically sorted)
        canonical_dict = {
            "e": jwk["e"],
            "kty": jwk["kty"],
            "n": jwk["n"],
        }
    else:
        raise ValueError(f"unsupported key type: {kty}")

    # JSON with sorted keys, no whitespace per RFC 7638 Section 3
    canonical = json.dumps(canonical_dict, separators=(",", ":"), sort_keys=True)
    digest = hashlib.sha256(canonical.encode("utf-8")).digest()
    return b64url_encode(digest)


def compute_access_token_hash(access_token: str) -> str:
    """Compute access token hash for ath claim per RFC 9449 Section 6.1.

    The ath claim is the base64url-encoded SHA-256 hash of the ASCII
    encoding of the access token value.

    Args:
        access_token: The access token string

    Returns:
        Base64url-encoded SHA-256 hash

    Example:
        >>> ath = compute_access_token_hash("eyJhbGciOiJSUzI1NiIs...")
    """
    digest = hashlib.sha256(access_token.encode("ascii")).digest()
    return b64url_encode(digest)


__all__ = [
    "b64url_encode",
    "b64url_decode",
    "compute_jwk_thumbprint",
    "compute_access_token_hash",
]
