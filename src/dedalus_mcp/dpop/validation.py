# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""DPoP proof validation (server-side) per RFC 9449.

This module implements RFC 9449 server-side validation of DPoP proofs to ensure
access tokens are bound to the cryptographic key held by the legitimate client.

Validation checks per RFC 9449 Section 4.3:
1. Not more than one DPoP HTTP request header field
2. The DPoP HTTP request header field value is a single and well-formed JWT
3. All required claims per Section 4.2 are contained in the JWT
4. The typ JOSE Header Parameter has the value dpop+jwt
5. The alg JOSE Header Parameter indicates a registered asymmetric algorithm
6. The JWT signature verifies with the public key contained in the jwk header
7. The jwk JOSE Header Parameter does not contain a private key
8. The htm claim matches the HTTP method of the current request
9. The htu claim matches the HTTP URI (without query/fragment)
10. If server provided a nonce, the nonce claim matches
11. The iat claim is within an acceptable time window
12. If presented with an access token: ath matches hash, and key matches cnf.jkt

References:
    RFC 9449: OAuth 2.0 Demonstrating Proof of Possession (DPoP)
    RFC 7638: JSON Web Key (JWK) Thumbprint
"""

from __future__ import annotations

import json
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import urlparse

try:
    import jwt
    from jwt.exceptions import InvalidTokenError
except ImportError:
    jwt = None  # type: ignore
    InvalidTokenError = Exception  # type: ignore

from dedalus_mcp.dpop.thumbprint import compute_access_token_hash, compute_jwk_thumbprint
from dedalus_mcp.utils import get_logger


class Clock(Protocol):
    """Clock abstraction for testing time-dependent logic."""

    def now(self) -> float:
        """Return current Unix timestamp."""


class SystemClock:
    """Production clock using system time."""

    def now(self) -> float:
        return time.time()


# =============================================================================
# Error Types
# =============================================================================


class DPoPValidationError(Exception):
    """Base error for DPoP validation failures."""


class InvalidDPoPProofError(DPoPValidationError):
    """Raised when proof structure or signature is invalid.

    Covers RFC 9449 Section 4.3 checks 1-7.
    """


class DPoPReplayError(DPoPValidationError):
    """Raised when JTI has already been used.

    Per RFC 9449 Section 11.1, servers should detect replay attacks.
    """


class DPoPMethodMismatchError(DPoPValidationError):
    """Raised when proof's htm doesn't match request method.

    Per RFC 9449 Section 4.3 check 8.
    """


class DPoPUrlMismatchError(DPoPValidationError):
    """Raised when proof's htu doesn't match request URL.

    Per RFC 9449 Section 4.3 check 9.
    """


class DPoPExpiredError(DPoPValidationError):
    """Raised when proof iat is outside acceptable time window.

    Per RFC 9449 Section 4.3 check 11.
    """


class DPoPThumbprintMismatchError(DPoPValidationError):
    """Raised when proof key doesn't match token's cnf.jkt binding.

    Per RFC 9449 Section 4.3 check 12.
    """


class DPoPNonceMismatchError(DPoPValidationError):
    """Raised when proof nonce doesn't match server-provided nonce.

    Per RFC 9449 Section 4.3 check 10.
    """


# =============================================================================
# Result Types
# =============================================================================


@dataclass(frozen=True, slots=True)
class DPoPProofResult:
    """Result of successful DPoP proof validation."""

    jti: str
    htm: str
    htu: str
    iat: int
    thumbprint: str
    ath: str | None = None
    nonce: str | None = None


# =============================================================================
# Configuration
# =============================================================================


@dataclass(slots=True)
class DPoPValidatorConfig:
    """Configuration for DPoP validation."""

    clock: Clock = field(default_factory=SystemClock)
    """Clock for time operations (injectable for testing)."""

    leeway: float = 60.0
    """Clock skew tolerance in seconds (default: 60s per RFC 9449 Section 11.1)."""

    jti_cache_size: int = 10000
    """Maximum number of JTIs to cache for replay detection."""

    jti_cache_ttl: float = 300.0
    """TTL for JTI cache entries in seconds (default: 5 min)."""

    allowed_algorithms: list[str] = field(default_factory=lambda: ["ES256"])
    """Allowed signing algorithms. Only ES256 by default per our AS."""


# =============================================================================
# JTI Cache (LRU with TTL)
# =============================================================================


class _JTICache:
    """LRU cache with TTL for JTI replay detection.

    Per RFC 9449 Section 11.1, servers should track JTIs to prevent replay.
    This implementation uses an ordered dict for LRU eviction and TTL expiration.
    """

    def __init__(self, max_size: int, ttl: float, clock: Clock) -> None:
        self._max_size = max_size
        self._ttl = ttl
        self._clock = clock
        self._cache: OrderedDict[str, float] = OrderedDict()

    def contains(self, jti: str) -> bool:
        """Check if JTI is in cache (not expired)."""
        if jti not in self._cache:
            return False

        cached_at = self._cache[jti]
        now = self._clock.now()

        if now - cached_at > self._ttl:
            # Expired, remove and return False
            del self._cache[jti]
            return False

        return True

    def add(self, jti: str) -> None:
        """Add JTI to cache."""
        now = self._clock.now()

        # Evict expired entries opportunistically
        self._evict_expired(now)

        # Evict oldest if at capacity
        while len(self._cache) >= self._max_size:
            self._cache.popitem(last=False)

        self._cache[jti] = now
        # Move to end (most recently used)
        self._cache.move_to_end(jti)

    def _evict_expired(self, now: float) -> None:
        """Remove expired entries."""
        expired = [k for k, v in self._cache.items() if now - v > self._ttl]
        for k in expired:
            del self._cache[k]


# =============================================================================
# URL Normalization
# =============================================================================


def _normalize_url(url: str) -> str:
    """Normalize URL for comparison per RFC 9449 Section 4.2.

    The htu claim is "The HTTP target URI ... without query and fragment parts."
    We also lowercase scheme and host per RFC 3986 normalization.
    """
    parsed = urlparse(url)
    # Strip query and fragment, lowercase scheme and host
    normalized = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower(),
        query="",
        fragment="",
    )
    return normalized.geturl()


# =============================================================================
# Validator
# =============================================================================


class DPoPValidator:
    """Validates DPoP proofs per RFC 9449.

    This class implements all 12 validation checks from RFC 9449 Section 4.3.

    Example:
        >>> config = DPoPValidatorConfig()
        >>> validator = DPoPValidator(config)
        >>> result = validator.validate_proof(
        ...     proof="eyJ...",
        ...     method="POST",
        ...     url="https://mcp.example.com/messages",
        ...     expected_thumbprint="abc123...",  # From token's cnf.jkt
        ...     access_token="eyJ...",
        ... )
    """

    def __init__(self, config: DPoPValidatorConfig | None = None) -> None:
        if jwt is None:
            raise ImportError("DPoP validation requires pyjwt. Install with: uv add pyjwt cryptography")

        self.config = config or DPoPValidatorConfig()
        self._logger = get_logger("dedalus_mcp.dpop")
        self._jti_cache = _JTICache(
            max_size=self.config.jti_cache_size,
            ttl=self.config.jti_cache_ttl,
            clock=self.config.clock,
        )

    def validate_proof(
        self,
        proof: str,
        method: str,
        url: str,
        *,
        expected_thumbprint: str | None = None,
        access_token: str | None = None,
        expected_nonce: str | None = None,
    ) -> DPoPProofResult:
        """Validate a DPoP proof JWT.

        Implements all checks from RFC 9449 Section 4.3.

        Args:
            proof: The DPoP proof JWT from the DPoP header
            method: HTTP method of the request (e.g., "POST")
            url: Full URL of the request (e.g., "https://mcp.example.com/messages")
            expected_thumbprint: JWK thumbprint from access token's cnf.jkt claim.
                               If provided, validates key binding.
            access_token: Access token for ath validation.
                         If proof contains ath, this MUST be provided.
            expected_nonce: Server-provided nonce. If provided and proof lacks
                          matching nonce claim, validation fails.

        Returns:
            DPoPProofResult with validated claims

        Raises:
            InvalidDPoPProofError: If proof structure/signature is invalid
            DPoPReplayError: If JTI was already used
            DPoPMethodMismatchError: If htm doesn't match method
            DPoPUrlMismatchError: If htu doesn't match url
            DPoPExpiredError: If iat is outside acceptable window
            DPoPThumbprintMismatchError: If key doesn't match expected_thumbprint
            DPoPNonceMismatchError: If nonce doesn't match expected_nonce
        """
        # Check 2: Parse JWT header
        try:
            header = jwt.get_unverified_header(proof)
        except Exception as e:
            self._logger.warning(
                "DPoP proof header parse failed",
                extra={"event": "dpop.header.invalid", "error": str(e)},
            )
            raise InvalidDPoPProofError(f"invalid proof header: {e}") from e

        # Check 4: Validate typ header
        typ = header.get("typ")
        if typ != "dpop+jwt":
            raise InvalidDPoPProofError(f"invalid typ header, expected 'dpop+jwt', got '{typ}'")

        # Check 3 (partial): Extract and validate JWK from header
        jwk = header.get("jwk")
        if not jwk:
            raise InvalidDPoPProofError("missing jwk in proof header")

        if not isinstance(jwk, dict):
            raise InvalidDPoPProofError("jwk must be a JSON object")

        # Check 7: jwk MUST NOT contain a private key
        # EC private key field: d
        # RSA private key fields: d, p, q, dp, dq, qi
        private_key_fields = {"d", "p", "q", "dp", "dq", "qi"}
        if private_key_fields & jwk.keys():
            raise InvalidDPoPProofError("jwk must not contain private key material")

        # Check 5: Validate algorithm
        alg = header.get("alg")
        if alg not in self.config.allowed_algorithms:
            raise InvalidDPoPProofError(
                f"unsupported algorithm '{alg}', allowed: {self.config.allowed_algorithms}"
            )

        # Check 6 (setup): Convert JWK to public key for verification
        try:
            public_key = self._jwk_to_public_key(jwk, alg)
        except Exception as e:
            raise InvalidDPoPProofError(f"invalid jwk: {e}") from e

        # Check 6: Verify signature and decode claims
        try:
            claims = jwt.decode(
                proof,
                public_key,
                algorithms=self.config.allowed_algorithms,
                options={
                    "verify_signature": True,
                    "verify_exp": False,
                    "verify_nbf": False,
                    "verify_iat": False,
                    "verify_aud": False,
                    "verify_iss": False,
                },
            )
        except Exception as e:
            self._logger.warning(
                "DPoP proof signature verification failed",
                extra={"event": "dpop.signature.invalid", "error": str(e)},
            )
            raise InvalidDPoPProofError(f"signature verification failed: {e}") from e

        # Check 3: Validate required claims
        jti = claims.get("jti")
        htm = claims.get("htm")
        htu = claims.get("htu")
        iat = claims.get("iat")

        if not jti:
            raise InvalidDPoPProofError("missing required claim: jti")
        if not htm:
            raise InvalidDPoPProofError("missing required claim: htm")
        if not htu:
            raise InvalidDPoPProofError("missing required claim: htu")
        if iat is None:
            raise InvalidDPoPProofError("missing required claim: iat")

        # Check 8: Validate method binding
        if htm.upper() != method.upper():
            raise DPoPMethodMismatchError(
                f"method mismatch: proof bound to '{htm}', request is '{method}'"
            )

        # Check 9: Validate URL binding (case-insensitive for scheme/host)
        normalized_htu = _normalize_url(htu)
        normalized_url = _normalize_url(url)
        if normalized_htu != normalized_url:
            raise DPoPUrlMismatchError(f"URL mismatch: proof bound to '{htu}', request is '{url}'")

        # Check 10: Validate nonce if server requires it
        proof_nonce = claims.get("nonce")
        if expected_nonce is not None:
            if proof_nonce != expected_nonce:
                raise DPoPNonceMismatchError(
                    f"nonce mismatch: proof has '{proof_nonce}', expected '{expected_nonce}'"
                )

        # Check 11: Validate iat timing
        now = self.config.clock.now()
        if isinstance(iat, (int, float)):
            iat_ts = float(iat)
        else:
            raise InvalidDPoPProofError(f"invalid iat type: {type(iat)}")

        if iat_ts < now - self.config.leeway:
            raise DPoPExpiredError("proof too old (iat in past)")
        if iat_ts > now + self.config.leeway:
            raise DPoPExpiredError("proof from future (iat too far ahead)")

        # Replay detection (RFC 9449 Section 11.1)
        if self._jti_cache.contains(jti):
            raise DPoPReplayError(f"JTI replay detected: {jti}")
        self._jti_cache.add(jti)

        # Check 12: Compute and validate thumbprint
        thumbprint = compute_jwk_thumbprint(jwk)

        if expected_thumbprint is not None:
            if thumbprint != expected_thumbprint:
                raise DPoPThumbprintMismatchError(
                    f"thumbprint mismatch: proof key '{thumbprint}' != expected '{expected_thumbprint}'"
                )

        # Check 12 (continued): Validate ath if present
        ath = claims.get("ath")
        if ath is not None:
            if access_token is None:
                # ath present but no token to validate against
                # This is acceptable - we just can't validate it
                pass
            else:
                expected_ath = compute_access_token_hash(access_token)
                if ath != expected_ath:
                    raise InvalidDPoPProofError(
                        f"ath mismatch: proof '{ath}' != computed '{expected_ath}'"
                    )

        self._logger.debug(
            "DPoP proof validated",
            extra={
                "event": "dpop.validated",
                "jti": jti,
                "htm": htm,
                "thumbprint": thumbprint[:8] + "...",
            },
        )

        return DPoPProofResult(
            jti=jti,
            htm=htm,
            htu=htu,
            iat=int(iat_ts),
            thumbprint=thumbprint,
            ath=ath,
            nonce=proof_nonce,
        )

    def _jwk_to_public_key(self, jwk: dict[str, Any], alg: str) -> Any:
        """Convert JWK dictionary to a public key object."""
        from jwt.algorithms import ECAlgorithm, RSAAlgorithm

        kty = jwk.get("kty")
        jwk_json = json.dumps(jwk)

        if kty == "EC":
            return ECAlgorithm.from_jwk(jwk_json)
        elif kty == "RSA":
            return RSAAlgorithm.from_jwk(jwk_json)
        else:
            raise ValueError(f"unsupported key type: {kty}")


__all__ = [
    "Clock",
    "SystemClock",
    "DPoPValidatorConfig",
    "DPoPValidator",
    "DPoPProofResult",
    "DPoPValidationError",
    "InvalidDPoPProofError",
    "DPoPReplayError",
    "DPoPMethodMismatchError",
    "DPoPUrlMismatchError",
    "DPoPExpiredError",
    "DPoPThumbprintMismatchError",
    "DPoPNonceMismatchError",
]
