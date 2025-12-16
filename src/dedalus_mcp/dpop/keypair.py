# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""DPoP keypair generation utilities.

This module provides functions for generating ES256 (P-256) keypairs for DPoP.
The keypairs are ephemeral and should be generated per-session or per-token.

References:
    RFC 9449 Section 2: Objectives (recommends ES256)
    RFC 7518 Section 3.4: ECDSA (ES256 = P-256 + SHA-256)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dedalus_mcp.dpop.thumbprint import b64url_encode

if TYPE_CHECKING:
    from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePrivateKey


def generate_dpop_keypair() -> tuple["EllipticCurvePrivateKey", dict[str, str]]:
    """Generate an ES256 (P-256) keypair for DPoP.

    Returns a private key object and the corresponding public key as a JWK dict.
    The private key is used for signing DPoP proofs, and the JWK is embedded
    in the proof header.

    Returns:
        Tuple of (private_key, public_jwk) where:
        - private_key: EllipticCurvePrivateKey for signing
        - public_jwk: Dict with kty, crv, x, y fields

    Example:
        >>> private_key, public_jwk = generate_dpop_keypair()
        >>> proof = generate_dpop_proof(private_key, "POST", "https://as.example.com/token")
        >>> thumbprint = compute_jwk_thumbprint(public_jwk)
    """
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.asymmetric import ec

    # Generate P-256 private key
    private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())

    # Extract public key coordinates
    public_key = private_key.public_key()
    public_numbers = public_key.public_numbers()

    # P-256 coordinates are 32 bytes (256 bits)
    coord_size = 32
    x_bytes = public_numbers.x.to_bytes(coord_size, byteorder="big")
    y_bytes = public_numbers.y.to_bytes(coord_size, byteorder="big")

    public_jwk = {
        "kty": "EC",
        "crv": "P-256",
        "x": b64url_encode(x_bytes),
        "y": b64url_encode(y_bytes),
    }

    return private_key, public_jwk


__all__ = ["generate_dpop_keypair"]
