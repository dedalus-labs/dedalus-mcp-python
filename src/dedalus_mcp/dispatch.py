# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Dispatch backend for privileged operations.

This module provides the interface for tools to execute authenticated HTTP
requests through connection handles. Two backend implementations are provided:

- `DirectDispatchBackend`: OSS mode - calls downstream APIs directly using
  credentials loaded from environment variables or local configuration.

- `EnclaveDispatchBackend`: Production mode - forwards requests to the
  Dedalus Enclave with DPoP-bound access tokens for secure credential isolation.

Security model:
    MCP server code specifies *what to call* (method, path, body).
    The enclave handles *credentials* and executes the request.
    Credentials never leave the enclave - only HTTP responses are returned.

The dispatch flow:
1. Tool calls `ctx.dispatch(connection, HttpRequest(...))`
2. Framework resolves connection name to handle
3. Handle format validated locally
4. Gateway validates authorization against org's connections at runtime
5. Backend executes the HTTP request (locally or via Enclave)
6. HttpResponse returned to tool

Example:
    >>> @server.tool()
    >>> async def create_issue(ctx: Context, title: str) -> dict:
    ...     response = await ctx.dispatch(HttpRequest(
    ...         method=HttpMethod.POST,
    ...         path="/repos/owner/repo/issues",
    ...         body={"title": title, "body": "Auto-created"},
    ...     ))
    ...     return response.body

References:
    /dcs/docs/design/dispatch-interface.md (security model)
"""

from __future__ import annotations

import hashlib
import hmac
import time
from enum import Enum, StrEnum
from typing import Any, Callable, Protocol, runtime_checkable
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .utils import get_logger

_logger = get_logger("dedalus_mcp.dispatch")


# =============================================================================
# HTTP Types (New Dispatch Model)
# =============================================================================


class HttpMethod(StrEnum):
    """HTTP methods supported by dispatch."""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


class HttpRequest(BaseModel):
    """HTTP request to execute against downstream API.

    Attributes:
        method: HTTP method (GET, POST, PUT, PATCH, DELETE)
        path: Request path including query string (e.g., "/repos/owner/repo/issues?state=open")
        body: Request body - dict/list serialized as JSON, str sent as-is
        headers: Additional headers (cannot override Authorization)
        timeout_ms: Request timeout; falls back to connection default if None
    """

    model_config = ConfigDict(extra="forbid")

    method: HttpMethod
    path: str = Field(..., min_length=1, description="Path with optional query string")
    body: dict[str, Any] | list[Any] | str | None = None
    headers: dict[str, str] | None = None
    timeout_ms: int | None = Field(default=None, ge=1000, le=300_000)

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        """Validate path and URL-encode query string if needed.

        Automatically encodes unsafe characters in query params (spaces,
        parentheses, quotes) while preserving REST API structure chars.
        This prevents "invalid uri character" errors from downstream.
        """
        if not v.startswith("/"):
            raise ValueError("path must start with '/'")

        # Split path and query, encode query params if present
        if "?" in v:
            path_part, query_part = v.split("?", 1)
            # Encode query while keeping structure chars (=&,.*) intact
            # This handles PostgREST operators like "NOT IN (...)" safely
            encoded_query = quote(query_part, safe="=&,.*-_~:")
            return f"{path_part}?{encoded_query}"
        return v

    @field_validator("headers")
    @classmethod
    def validate_headers(cls, v: dict[str, str] | None) -> dict[str, str] | None:
        """Reject headers that must be set by the dispatch backend."""
        if v is None:
            return None

        forbidden = {"authorization", "dpop"}
        bad = [name for name in v if name.lower() in forbidden]
        if bad:
            raise ValueError(f"headers must not include reserved header(s): {', '.join(sorted(bad))}")

        return v


class HttpResponse(BaseModel):
    """HTTP response from downstream API.

    Attributes:
        status: HTTP status code (100-599)
        headers: Response headers
        body: Response body - parsed JSON if applicable, else raw string
    """

    status: int = Field(..., ge=100, le=599)
    headers: dict[str, str] = Field(default_factory=dict)
    body: dict[str, Any] | list[Any] | str | None = None


class DispatchErrorCode(str, Enum):
    """Error codes for dispatch failures.

    These represent infrastructure failures - NOT HTTP 4xx/5xx from downstream.
    A downstream 404 is still success=True with response.status=404.

    Wire format uses SCREAMING_CASE for machine-readability and grep-ability.
    """

    CONNECTION_NOT_FOUND = "CONNECTION_NOT_FOUND"
    CONNECTION_REVOKED = "CONNECTION_REVOKED"
    CONNECTION_SUSPENDED = "CONNECTION_SUSPENDED"
    ORG_MISMATCH = "ORG_MISMATCH"
    DECRYPTION_FAILED = "DECRYPTION_FAILED"
    INVALID_REQUEST = "INVALID_REQUEST"
    BAD_REQUEST = "BAD_REQUEST"
    DOWNSTREAM_TIMEOUT = "DOWNSTREAM_TIMEOUT"
    DOWNSTREAM_UNREACHABLE = "DOWNSTREAM_UNREACHABLE"
    DOWNSTREAM_TLS_ERROR = "DOWNSTREAM_TLS_ERROR"
    DOWNSTREAM_AUTH_FAILURE = "DOWNSTREAM_AUTH_FAILURE"
    DOWNSTREAM_RATE_LIMITED = "DOWNSTREAM_RATE_LIMITED"
    ENCLAVE_UNAVAILABLE = "ENCLAVE_UNAVAILABLE"


class DispatchError(BaseModel):
    """Infrastructure error from dispatch.

    Attributes:
        code: Structured error code for programmatic handling
        message: Human-readable error description
        retryable: Whether the operation may succeed on retry
    """

    code: DispatchErrorCode
    message: str
    retryable: bool = False


class DispatchResponse(BaseModel):
    """Response from ctx.dispatch().

    success=True: Got a response from downstream (even HTTP 4xx/5xx).
    success=False: Infrastructure failure (couldn't reach downstream).

    Attributes:
        success: Whether we got an HTTP response from downstream
        response: HTTP response if success=True
        error: Structured error if success=False
    """

    model_config = ConfigDict(extra="forbid")

    success: bool
    response: HttpResponse | None = None
    error: DispatchError | None = None

    @classmethod
    def ok(cls, response: HttpResponse) -> "DispatchResponse":
        """Factory for successful dispatch."""
        return cls(success=True, response=response)

    @classmethod
    def fail(cls, code: DispatchErrorCode, message: str, *, retryable: bool = False) -> "DispatchResponse":
        """Factory for failed dispatch."""
        return cls(success=False, error=DispatchError(code=code, message=message, retryable=retryable))


# =============================================================================
# Wire Format (Internal)
# =============================================================================


class DispatchWireRequest(BaseModel):
    """Wire format sent to gateway/enclave.

    This is the internal format - users interact with HttpRequest.

    Attributes:
        connection_handle: Resolved handle (e.g., "ddls:conn:abc123")
        request: The HTTP request to execute
        authorization: Optional JWT from MCP server request context for dispatch auth
    """

    connection_handle: str = Field(..., min_length=1)
    request: HttpRequest
    authorization: str | None = None

    @field_validator("connection_handle")
    @classmethod
    def validate_handle_format(cls, v: str) -> str:
        """Validate connection handle format."""
        if not v.startswith("ddls:conn"):
            raise ValueError("connection_handle must start with 'ddls:conn'")
        return v


# =============================================================================
# Backend Protocol
# =============================================================================


@runtime_checkable
class DispatchBackend(Protocol):
    """Protocol for dispatch backend implementations.

    Backends handle execution of authenticated HTTP requests, either
    locally (DirectDispatchBackend) or via the Enclave (EnclaveDispatchBackend).
    """

    async def dispatch(self, request: DispatchWireRequest) -> DispatchResponse:
        """Execute an authenticated HTTP request.

        Args:
            request: Wire request with connection handle and HTTP request

        Returns:
            DispatchResponse with HTTP response or error
        """
        ...


# =============================================================================
# Direct Dispatch Backend (OSS Mode)
# =============================================================================


# Type for credential resolver: handle → (base_url, header_name, header_value)
CredentialResolver = Callable[[str], tuple[str, str, str]]


class DirectDispatchBackend:
    """Dispatch backend for OSS mode with local credentials.

    This backend executes HTTP requests directly using credentials resolved
    from environment variables or local configuration.

    Useful for:
    - Local development without Enclave access
    - Self-hosted deployments with direct credential management
    - Testing and CI environments

    Example:
        >>> def resolve_creds(handle: str) -> tuple[str, str, str]:
        ...     # Return (base_url, header_name, header_value)
        ...     return ("https://api.github.com", "Authorization", f"Bearer {os.getenv('GITHUB_TOKEN')}")
        >>> backend = DirectDispatchBackend(credential_resolver=resolve_creds)
        >>> response = await backend.dispatch(wire_request)
    """

    def __init__(self, credential_resolver: CredentialResolver | None = None) -> None:
        """Initialize direct dispatch backend.

        Args:
            credential_resolver: Function that resolves connection handle to
                (base_url, header_name, header_value). If None, dispatch will fail.
        """
        self._resolver = credential_resolver

    async def dispatch(self, request: DispatchWireRequest) -> DispatchResponse:
        """Execute HTTP request with resolved credentials.

        Args:
            request: Wire request with connection handle and HTTP request

        Returns:
            DispatchResponse with HTTP response or error
        """
        if self._resolver is None:
            return DispatchResponse.fail(
                DispatchErrorCode.CONNECTION_NOT_FOUND,
                "No credential resolver configured for direct dispatch",
            )

        try:
            base_url, header_name, header_value = self._resolver(request.connection_handle)
        except Exception as e:
            _logger.warning(
                "credential resolution failed",
                extra={"event": "dispatch.resolve.error", "handle": request.connection_handle, "error": str(e)},
            )
            return DispatchResponse.fail(
                DispatchErrorCode.CONNECTION_NOT_FOUND,
                f"Failed to resolve credentials: {e}",
            )

        try:
            import httpx
        except ImportError:
            return DispatchResponse.fail(
                DispatchErrorCode.DOWNSTREAM_UNREACHABLE,
                "httpx not installed; required for HTTP dispatch",
            )

        # Build full URL
        url = f"{base_url.rstrip('/')}{request.request.path}"

        # Build headers
        headers: dict[str, str] = {header_name: header_value}
        if request.request.headers:
            headers.update(request.request.headers)

        # Determine timeout
        timeout = (request.request.timeout_ms or 30_000) / 1000.0

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.request(
                    method=request.request.method.value,
                    url=url,
                    headers=headers,
                    json=request.request.body if isinstance(request.request.body, (dict, list)) else None,
                    content=request.request.body if isinstance(request.request.body, str) else None,
                )

            # Parse response body
            body: dict[str, Any] | list[Any] | str | None = None
            content_type = response.headers.get("content-type", "")
            if "application/json" in content_type:
                try:
                    body = response.json()
                except Exception:
                    body = response.text
            elif response.text:
                body = response.text

            http_response = HttpResponse(
                status=response.status_code,
                headers=dict(response.headers),
                body=body,
            )

            _logger.debug(
                "dispatch succeeded",
                extra={
                    "event": "dispatch.success",
                    "handle": request.connection_handle,
                    "status": response.status_code,
                },
            )

            return DispatchResponse.ok(http_response)

        except httpx.TimeoutException:
            return DispatchResponse.fail(
                DispatchErrorCode.DOWNSTREAM_TIMEOUT,
                f"Request timed out after {timeout}s",
                retryable=True,
            )
        except httpx.ConnectError as e:
            return DispatchResponse.fail(
                DispatchErrorCode.DOWNSTREAM_UNREACHABLE,
                f"Could not connect to downstream: {e}",
                retryable=True,
            )
        except Exception as e:
            _logger.exception(
                "unexpected dispatch error",
                extra={"event": "dispatch.error", "handle": request.connection_handle, "error": str(e)},
            )
            return DispatchResponse.fail(
                DispatchErrorCode.DOWNSTREAM_UNREACHABLE,
                f"Unexpected error: {e}",
            )


# =============================================================================
# Enclave Dispatch Backend
# =============================================================================


class EnclaveDispatchBackend:
    """Dispatch backend that forwards to the Dedalus Enclave.

    This backend sends HTTP requests to the Enclave with DPoP-bound access tokens.
    The Enclave securely manages credentials and executes operations on behalf
    of the MCP server.

    Runner authentication uses HMAC signatures (not JWT) for identifying deployments.
    The deployment_id and auth_secret are injected at deploy time via environment.

    Wire format (POST /dispatch):
        Authorization: DPoP {access_token}
        DPoP: {dpop_proof}
        X-Dedalus-Timestamp: {unix_timestamp}
        X-Dedalus-Deployment: {deployment_id}
        X-Dedalus-Signature: {hmac_signature}
        Content-Type: application/json

        {
            "connection_handle": "ddls:conn:abc123",
            "request": {
                "method": "POST",
                "path": "/repos/owner/repo/issues",
                "body": {"title": "Bug"}
            }
        }

    Example:
        >>> backend = EnclaveDispatchBackend(
        ...     enclave_url="https://enclave.dedalus.cloud",
        ...     access_token=token,
        ...     dpop_key=key,
        ...     deployment_id="dep_01ABC",
        ...     auth_secret=b"32-byte-secret...",
        ... )
        >>> response = await backend.dispatch(wire_request)
    """

    def __init__(
        self,
        enclave_url: str,
        access_token: str,
        dpop_key: Any | None = None,
        deployment_id: str | None = None,
        auth_secret: bytes | None = None,
        timeout: float = 30.0,
    ) -> None:
        """Initialize enclave backend.

        Args:
            enclave_url: Base URL of the Dispatch Gateway
            access_token: DPoP-bound user access token
            dpop_key: ES256 private key for DPoP proof generation
            deployment_id: Deployment ID for HMAC auth (from DEDALUS_DEPLOYMENT_ID)
            auth_secret: 32-byte HMAC secret (from DEDALUS_AUTH_SECRET, base64)
            timeout: Request timeout in seconds
        """
        self._enclave_url = enclave_url.rstrip("/")
        self._access_token = access_token
        self._dpop_key = dpop_key
        self._deployment_id = deployment_id
        self._auth_secret = auth_secret
        self._timeout = timeout

    async def dispatch(self, request: DispatchWireRequest) -> DispatchResponse:
        """Forward HTTP request to Enclave.

        Args:
            request: Wire request with connection handle and HTTP request

        Returns:
            DispatchResponse with HTTP response or error
        """
        try:
            import httpx
        except ImportError:
            return DispatchResponse.fail(
                DispatchErrorCode.DOWNSTREAM_UNREACHABLE,
                "httpx not installed; required for Enclave dispatch",
            )

        dispatch_url = f"{self._enclave_url.rstrip('/')}/dispatch"

        # Build wire format body first (needed for HMAC)
        body = {
            "connection_handle": request.connection_handle,
            "request": {
                "method": request.request.method.value,
                "path": request.request.path,
                "body": request.request.body,
                "headers": request.request.headers,
                "timeout_ms": request.request.timeout_ms,
            },
        }

        # Serialize body for HMAC computation
        import json
        body_bytes = json.dumps(body, separators=(",", ":")).encode()

        # Build headers
        headers = {"Content-Type": "application/json"}

        # Add HMAC runner authentication
        if self._deployment_id and self._auth_secret:
            hmac_headers = self._sign_request(body_bytes)
            headers.update(hmac_headers)

        # Use per-request auth if provided, otherwise fall back to init token
        access_token = request.authorization or self._access_token

        # Add authorization headers (only if token present)
        if access_token:
            if self._dpop_key is not None:
                headers["Authorization"] = f"DPoP {access_token}"
                headers["DPoP"] = self._generate_dpop_proof(dispatch_url, "POST")
            else:
                headers["Authorization"] = f"Bearer {access_token}"
        else:
            _logger.warning(
                "no access token available for dispatch",
                extra={"event": "dispatch.no_token", "handle": request.connection_handle},
            )

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(dispatch_url, content=body_bytes, headers=headers)

            if response.status_code == 401:
                return DispatchResponse.fail(
                    DispatchErrorCode.CONNECTION_REVOKED,
                    f"Authentication failed (401): {response.text}",
                )

            if response.status_code == 403:
                return DispatchResponse.fail(
                    DispatchErrorCode.CONNECTION_NOT_FOUND,
                    f"Authorization failed (403): {response.text}",
                )

            if response.status_code >= 400:
                return DispatchResponse.fail(
                    DispatchErrorCode.DOWNSTREAM_UNREACHABLE,
                    f"Enclave error ({response.status_code}): {response.text}",
                )

            data = response.json()

            # Enclave returns canonical DispatchResponse format
            if data.get("success"):
                http_resp = data.get("response", {})
                return DispatchResponse.ok(
                    HttpResponse(
                        status=http_resp.get("status", 200),
                        headers=http_resp.get("headers", {}),
                        body=http_resp.get("body"),
                    )
                )
            else:
                error_data = data.get("error", {})
                code_str = error_data.get("code", "DOWNSTREAM_UNREACHABLE")
                try:
                    code = DispatchErrorCode(code_str)
                except ValueError:
                    _logger.warning(
                        "unknown dispatch error code",
                        extra={"event": "dispatch.unknown_code", "code": code_str},
                    )
                    code = DispatchErrorCode.DOWNSTREAM_UNREACHABLE
                return DispatchResponse.fail(
                    code,
                    error_data.get("message", "Unknown error"),
                    retryable=error_data.get("retryable", False),
                )

        except httpx.TimeoutException:
            return DispatchResponse.fail(
                DispatchErrorCode.DOWNSTREAM_TIMEOUT,
                "Enclave request timed out",
                retryable=True,
            )
        except httpx.RequestError as e:
            return DispatchResponse.fail(
                DispatchErrorCode.DOWNSTREAM_UNREACHABLE,
                f"Enclave request failed: {e}",
                retryable=True,
            )
        except Exception as e:
            _logger.exception(
                "unexpected enclave dispatch error",
                extra={"event": "dispatch.enclave.error", "error": str(e)},
            )
            return DispatchResponse.fail(
                DispatchErrorCode.DOWNSTREAM_UNREACHABLE,
                f"Unexpected error: {e}",
            )

    def _sign_request(self, body: bytes) -> dict[str, str]:
        """Generate HMAC signature headers for runner authentication.

        Signature: HMAC-SHA256(auth_secret, "{timestamp}:{deployment_id}:{sha256(body)}")

        Args:
            body: Request body bytes

        Returns:
            Headers dict with X-Dedalus-Timestamp, X-Dedalus-Deployment, X-Dedalus-Signature
        """
        if not self._deployment_id or not self._auth_secret:
            return {}

        timestamp = str(int(time.time()))
        body_hash = hashlib.sha256(body).hexdigest()
        message = f"{timestamp}:{self._deployment_id}:{body_hash}".encode()
        signature = hmac.new(self._auth_secret, message, hashlib.sha256).hexdigest()

        return {
            "X-Dedalus-Timestamp": timestamp,
            "X-Dedalus-Deployment": self._deployment_id,
            "X-Dedalus-Signature": signature,
        }

    def _generate_dpop_proof(self, url: str, method: str) -> str:
        """Generate DPoP proof JWT for the request.

        Args:
            url: Request URL (becomes htu claim)
            method: HTTP method (becomes htm claim)

        Returns:
            DPoP proof JWT string
        """
        if self._dpop_key is None:
            return ""

        from dedalus_mcp.dpop import generate_dpop_proof

        return generate_dpop_proof(
            private_key=self._dpop_key,
            method=method,
            url=url,
            access_token=self._access_token,
        )


def create_dispatch_backend_from_env() -> DispatchBackend:
    """Create dispatch backend from environment variables.

    If DEDALUS_DISPATCH_URL is set, returns EnclaveDispatchBackend configured
    for Dedalus Cloud. Otherwise returns DirectDispatchBackend for OSS mode.

    Environment variables (Dedalus Cloud):
        DEDALUS_DISPATCH_URL: Dispatch Gateway URL (internal, not public)
        DEDALUS_DEPLOYMENT_ID: Deployment ID for HMAC auth
        DEDALUS_AUTH_SECRET: Base64-encoded 32-byte HMAC secret
        DEDALUS_ACCESS_TOKEN: User's DPoP-bound access token (set per-request)

    Returns:
        Configured dispatch backend

    Raises:
        RuntimeError: If running in Lambda without DEDALUS_DISPATCH_URL configured
    """
    import base64
    import os

    dispatch_url = os.getenv("DEDALUS_DISPATCH_URL")

    if dispatch_url:
        deployment_id = os.getenv("DEDALUS_DEPLOYMENT_ID")
        auth_secret_b64 = os.getenv("DEDALUS_AUTH_SECRET")
        auth_secret = base64.b64decode(auth_secret_b64) if auth_secret_b64 else None

        _logger.info(
            "dispatch backend configured",
            extra={"event": "dispatch.init", "backend": "enclave", "url": dispatch_url},
        )

        # Access token and DPoP key are typically set per-request, not at init
        # This factory is for the runner identity; user auth is added later
        return EnclaveDispatchBackend(
            enclave_url=dispatch_url,
            access_token="",  # Set per-request via context
            deployment_id=deployment_id,
            auth_secret=auth_secret,
        )

    # Detect managed deployment - missing DEDALUS_DISPATCH_URL is a config error
    is_managed = os.getenv("AWS_LAMBDA_FUNCTION_NAME") or os.getenv("AWS_EXECUTION_ENV")
    if is_managed:
        _logger.error(
            "DEDALUS_DISPATCH_URL not set in managed environment. "
            "Dispatch to external services will fail.",
            extra={"event": "dispatch.init.error", "backend": "none"},
        )
        raise RuntimeError(
            "DEDALUS_DISPATCH_URL required in managed deployments. "
            "Verify deployment configuration injects dispatch credentials."
        )

    _logger.debug(
        "dispatch backend configured",
        extra={"event": "dispatch.init", "backend": "direct"},
    )
    return DirectDispatchBackend()


__all__ = [
    # HTTP types
    "HttpMethod",
    "HttpRequest",
    "HttpResponse",
    # Dispatch types
    "DispatchErrorCode",
    "DispatchError",
    "DispatchResponse",
    "DispatchWireRequest",
    # Backend protocol and implementations
    "DispatchBackend",
    "DirectDispatchBackend",
    "EnclaveDispatchBackend",
    "CredentialResolver",
    "create_dispatch_backend_from_env",
]
