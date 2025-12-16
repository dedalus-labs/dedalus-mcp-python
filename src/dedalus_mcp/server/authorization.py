# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Authorization scaffolding for Streamable HTTP transports.

This module prepares Dedalus MCP for an OAuth 2.1 protected-resource flow without
requiring the authorization server to be available at development time.

Key pieces:

* :class:`AuthorizationConfig` – opt-in server configuration.
* :class:`AuthorizationProvider` protocol – pluggable token validation.
* :class:`AuthorizationManager` – serves protected-resource metadata and wraps ASGI apps with
  bearer-token enforcement.

Implementations can supply their own provider that validates tokens against a
real authorization server once available.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from ..utils import get_logger


try:  # starlette is optional – only required for streamable HTTP deployments
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request
    from starlette.responses import JSONResponse, Response
    from starlette.routing import Route
except ImportError:
    BaseHTTPMiddleware = None  # type: ignore
    Request = None  # type: ignore
    JSONResponse = None  # type: ignore
    Response = None  # type: ignore
    Route = None  # type: ignore


@dataclass(slots=True)
class AuthorizationConfig:
    """Server-side authorization configuration."""

    enabled: bool = False
    metadata_path: str = "/.well-known/oauth-protected-resource"
    authorization_servers: list[str] = field(default_factory=lambda: ["https://as.dedaluslabs.ai"])
    required_scopes: list[str] = field(default_factory=list)
    cache_ttl: int = 300
    fail_open: bool = False
    require_dpop: bool = False
    """If True, require DPoP-bound tokens (Authorization: DPoP) instead of Bearer."""
    dpop_leeway: float = 60.0
    """Clock skew tolerance for DPoP proof validation."""


@dataclass(slots=True)
class AuthorizationContext:
    """Context returned by providers after successful validation."""

    subject: str | None
    scopes: list[str]
    claims: dict[str, Any]


class AuthorizationError(Exception):
    """Raised when token validation fails."""


def parse_authorization_token(auth_header: str) -> str | None:
    """Extract token from Authorization header (Bearer or DPoP scheme).

    Args:
        auth_header: Authorization header value (e.g., "Bearer token" or "DPoP token")

    Returns:
        Token string, or None if header format is invalid
    """
    if not auth_header:
        return None

    auth_lower = auth_header.lower()
    if auth_lower.startswith("bearer "):
        return auth_header[7:].strip()
    if auth_lower.startswith("dpop "):
        return auth_header[5:].strip()

    return None


class AuthorizationProvider(Protocol):
    async def validate(self, token: str) -> AuthorizationContext:
        """Validate a bearer token and return the associated context."""


class _NoopAuthorizationProvider:
    async def validate(self, token: str) -> AuthorizationContext:
        raise AuthorizationError("authorization provider not configured")


class AuthorizationManager:
    """Coordinates metadata serving and ASGI middleware for authorization."""

    def __init__(self, config: AuthorizationConfig, provider: AuthorizationProvider | None = None) -> None:
        self.config = config
        self._provider: AuthorizationProvider = provider or _NoopAuthorizationProvider()
        self._logger = get_logger("dedalus_mcp.authorization")

    @property
    def enabled(self) -> bool:
        return self.config.enabled

    def set_provider(self, provider: AuthorizationProvider) -> None:
        self._provider = provider

    def get_required_scopes(self) -> list[str]:
        """Return the list of required scopes for this server."""
        return list(self.config.required_scopes)

    # ------------------------------------------------------------------
    # Starlette integration helpers (lazy imports to avoid hard deps)
    # ------------------------------------------------------------------

    def starlette_route(self) -> Route:
        if Route is None or JSONResponse is None:
            raise RuntimeError("starlette must be installed to use HTTP authorization")

        async def metadata_endpoint(request: Request) -> Response:
            resource = self._canonical_resource(request)
            payload = {
                "resource": resource,
                "authorization_servers": self.config.authorization_servers,
                "scopes_supported": self.config.required_scopes,
            }
            headers = {"Cache-Control": f"public, max-age={self.config.cache_ttl}"}
            return JSONResponse(payload, headers=headers)

        return Route(self.config.metadata_path, metadata_endpoint, methods=["GET"])

    def wrap_asgi(self, app: Callable) -> Callable:
        if BaseHTTPMiddleware is None or Request is None or JSONResponse is None:
            raise RuntimeError("starlette must be installed to use HTTP authorization")

        manager = self

        class _Middleware(BaseHTTPMiddleware):
            async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:  # type: ignore[override]
                if request.url.path == manager.config.metadata_path:
                    return await call_next(request)

                auth_header = request.headers.get("authorization")
                if not auth_header:
                    return manager._challenge_response("missing authorization header")

                # Parse authorization scheme
                auth_lower = auth_header.lower()
                if manager.config.require_dpop:
                    if not auth_lower.startswith("dpop "):
                        return manager._challenge_response("DPoP-bound token required")
                    token = auth_header[5:].strip()
                    dpop_proof = request.headers.get("dpop")
                    if not dpop_proof:
                        return manager._challenge_response("missing DPoP proof header")
                else:
                    if not auth_lower.startswith("bearer "):
                        return manager._challenge_response("missing bearer token")
                    token = auth_header[7:].strip()
                    dpop_proof = None

                try:
                    context = await manager._provider.validate(token)

                    # If DPoP required, validate the proof
                    if manager.config.require_dpop and dpop_proof:
                        await manager._validate_dpop_proof(request, dpop_proof, token, context.claims)

                    request.scope["dedalus_mcp.auth"] = context
                    return await call_next(request)
                except AuthorizationError as exc:
                    manager._logger.warning(
                        "authorization failed", extra={"event": "auth.jwt.reject", "reason": str(exc)}
                    )
                    if manager.config.fail_open:
                        manager._logger.warning(
                            "authorization fail-open engaged; allowing request", extra={"event": "auth.fail_open"}
                        )
                        request.scope["dedalus_mcp.auth"] = None
                        return await call_next(request)
                    return manager._challenge_response(str(exc))

        return _Middleware(app)

    async def _validate_dpop_proof(
        self, request: Request, proof: str, access_token: str, claims: dict[str, Any]
    ) -> None:
        """Validate DPoP proof against request and token binding."""
        from dedalus_mcp.dpop import DPoPValidator, DPoPValidatorConfig, DPoPValidationError

        config = DPoPValidatorConfig(leeway=self.config.dpop_leeway)
        validator = DPoPValidator(config)

        # Get expected thumbprint from token's cnf.jkt claim
        cnf = claims.get("cnf", {})
        expected_thumbprint = cnf.get("jkt") if isinstance(cnf, dict) else None

        # Build full URL for htu validation
        url = str(request.url)

        try:
            validator.validate_proof(
                proof=proof,
                method=request.method,
                url=url,
                expected_thumbprint=expected_thumbprint,
                access_token=access_token,
            )
        except DPoPValidationError as exc:
            raise AuthorizationError(f"DPoP validation failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _challenge_response(self, reason: str | None = None) -> Response:
        if JSONResponse is None:
            msg = "starlette must be installed to use HTTP authorization"
            raise RuntimeError(msg)

        # RFC 9728 Protected Resource Metadata (MCP 2025-06-18+).
        # For MCP 2025-03-26, clients would use /.well-known/oauth-authorization-server.
        # We emit resource_metadata unconditionally because:
        # 1. The 401 happens before MCP protocol negotiation (no version yet)
        # 2. RFC 6750 says clients SHOULD ignore unknown WWW-Authenticate parameters
        scheme = "DPoP" if self.config.require_dpop else "Bearer"
        challenge = f'{scheme} error="invalid_token", resource_metadata="{self.config.metadata_path}"'

        if reason:
            # Escape quotes in error_description
            safe_reason = reason.replace('"', '\\"')
            challenge += f', error_description="{safe_reason}"'

        headers = {"WWW-Authenticate": challenge}
        payload = {"error": "unauthorized", "detail": reason}
        return JSONResponse(payload, status_code=401, headers=headers)

    def _canonical_resource(self, request: Request) -> str:
        # Construct scheme://host[:port] without trailing slash
        scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
        host = request.headers.get("x-forwarded-host", request.headers.get("host", ""))
        if not host:
            host = request.url.netloc
        base = f"{scheme}://{host}"
        return base.rstrip("/")


__all__ = [
    "AuthorizationConfig",
    "AuthorizationContext",
    "AuthorizationError",
    "AuthorizationManager",
    "AuthorizationProvider",
]
