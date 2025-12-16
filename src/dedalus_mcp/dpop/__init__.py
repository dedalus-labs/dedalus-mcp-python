# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""DPoP (Demonstrating Proof of Possession) - RFC 9449 implementation.

This package provides a complete, RFC 9449-compliant DPoP implementation for both
client-side (proof generation) and server-side (proof validation) use cases.

Architecture:
    Client (Product API) ──generates proof──> Server (MCP Server/AS)
                                               │
                                               └─validates proof─> DPoPValidator

Public API:

    Client-side (proof generation):
        - generate_dpop_keypair(): Create ES256 keypair for DPoP
        - generate_dpop_proof(): Create DPoP proof JWT
        - DPoPAuth: HTTPX auth handler for automatic header injection

    Server-side (proof validation):
        - DPoPValidator: Validates incoming DPoP proofs
        - DPoPValidatorConfig: Configuration for validation

    Shared utilities:
        - compute_jwk_thumbprint(): RFC 7638 JWK thumbprint
        - compute_access_token_hash(): Hash for ath claim

    Error types:
        - DPoPValidationError: Base error class
        - InvalidDPoPProofError: Structure/signature failures
        - DPoPReplayError: JTI reuse detection
        - DPoPMethodMismatchError: HTTP method binding violation
        - DPoPUrlMismatchError: URL binding violation
        - DPoPExpiredError: Timestamp out of window
        - DPoPThumbprintMismatchError: Key binding mismatch

Example (client-side):
    >>> from dedalus_mcp.dpop import generate_dpop_keypair, generate_dpop_proof
    >>>
    >>> # Generate keypair
    >>> private_key, public_jwk = generate_dpop_keypair()
    >>>
    >>> # Generate proof for token endpoint
    >>> proof = generate_dpop_proof(
    ...     private_key=private_key,
    ...     method="POST",
    ...     url="https://as.example.com/token",
    ... )

Example (server-side):
    >>> from dedalus_mcp.dpop import DPoPValidator
    >>>
    >>> validator = DPoPValidator()
    >>> result = validator.validate_proof(
    ...     proof=dpop_header_value,
    ...     method=request.method,
    ...     url=str(request.url),
    ...     expected_thumbprint=token_cnf_jkt,
    ...     access_token=access_token,
    ... )

References:
    RFC 9449: OAuth 2.0 Demonstrating Proof of Possession (DPoP)
    RFC 7638: JSON Web Key (JWK) Thumbprint
    RFC 7515: JSON Web Signature (JWS)
"""

from dedalus_mcp.dpop.validation import (
    Clock,
    SystemClock,
    DPoPValidator,
    DPoPValidatorConfig,
    DPoPProofResult,
    DPoPValidationError,
    InvalidDPoPProofError,
    DPoPReplayError,
    DPoPMethodMismatchError,
    DPoPUrlMismatchError,
    DPoPExpiredError,
    DPoPThumbprintMismatchError,
    DPoPNonceMismatchError,
)
from dedalus_mcp.dpop.thumbprint import compute_jwk_thumbprint, compute_access_token_hash
from dedalus_mcp.dpop.proof import generate_dpop_proof, DPoPAuth, BearerAuth
from dedalus_mcp.dpop.keypair import generate_dpop_keypair

__all__ = [
    # Client-side: proof generation
    "generate_dpop_keypair",
    "generate_dpop_proof",
    "DPoPAuth",
    "BearerAuth",
    # Server-side: validation
    "Clock",
    "SystemClock",
    "DPoPValidator",
    "DPoPValidatorConfig",
    "DPoPProofResult",
    # Shared utilities
    "compute_jwk_thumbprint",
    "compute_access_token_hash",
    # Error types
    "DPoPValidationError",
    "InvalidDPoPProofError",
    "DPoPReplayError",
    "DPoPMethodMismatchError",
    "DPoPUrlMismatchError",
    "DPoPExpiredError",
    "DPoPThumbprintMismatchError",
    "DPoPNonceMismatchError",
]
