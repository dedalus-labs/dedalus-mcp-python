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
3. Connection gate validates handle against JWT's `ddls:connections` claim
4. Backend executes the HTTP request (locally or via Enclave)
5. HttpResponse returned to tool

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

from enum import Enum
from typing import Any, Callable, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .utils import get_logger

_logger = get_logger("dedalus_mcp.dispatch")


# =============================================================================
# HTTP Types (New Dispatch Model)
# =============================================================================


class HttpMethod(str, Enum):
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
        """Validate path starts with /."""
        if not v.startswith("/"):
            raise ValueError("path must start with '/'")
        return v

    @field_validator("headers")
    @classmethod
    def validate_headers(cls, v: dict[str, str] | None) -> dict[str, str] | None:
        """Ensure Authorization cannot be overridden."""
        if v is None:
            return v
        forbidden = {"authorization", "x-runner-token", "dpop"}
        for key in v:
            if key.lower() in forbidden:
                raise ValueError(f"header '{key}' cannot be set via dispatch")
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
    """

    CONNECTION_NOT_FOUND = "connection_not_found"
    CONNECTION_REVOKED = "connection_revoked"
    DECRYPTION_FAILED = "decryption_failed"
    DOWNSTREAM_TIMEOUT = "downstream_timeout"
    DOWNSTREAM_UNREACHABLE = "downstream_unreachable"
    DOWNSTREAM_TLS_ERROR = "downstream_tls_error"


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
    """

    connection_handle: str = Field(..., min_length=1)
    request: HttpRequest

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


# Type for credential resolver: handle → (base_url, auth_header_value)
CredentialResolver = Callable[[str], tuple[str, str]]


class DirectDispatchBackend:
    """Dispatch backend for OSS mode with local credentials.

    This backend executes HTTP requests directly using credentials resolved
    from environment variables or local configuration.

    Useful for:
    - Local development without Enclave access
    - Self-hosted deployments with direct credential management
    - Testing and CI environments

    Example:
        >>> def resolve_creds(handle: str) -> tuple[str, str]:
        ...     # Return (base_url, "Bearer <token>")
        ...     return ("https://api.github.com", f"Bearer {os.getenv('GITHUB_TOKEN')}")
        >>> backend = DirectDispatchBackend(credential_resolver=resolve_creds)
        >>> response = await backend.dispatch(wire_request)
    """

    def __init__(self, credential_resolver: CredentialResolver | None = None) -> None:
        """Initialize direct dispatch backend.

        Args:
            credential_resolver: Function that resolves connection handle to
                (base_url, auth_header_value). If None, dispatch will fail.
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
            base_url, auth_header = self._resolver(request.connection_handle)
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
        headers: dict[str, str] = {"Authorization": auth_header}
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

    Wire format (POST /dispatch):
        Authorization: DPoP {access_token}
        DPoP: {dpop_proof}
        X-Runner-Token: {runner_token}
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
        ...     runner_token=runner_jwt,
        ... )
        >>> response = await backend.dispatch(wire_request)
    """

    def __init__(
        self,
        enclave_url: str,
        access_token: str,
        dpop_key: Any | None = None,
        runner_token: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        """Initialize enclave backend.

        Args:
            enclave_url: Base URL of the Dispatch Gateway
            access_token: DPoP-bound user access token
            dpop_key: ES256 private key for DPoP proof generation
            runner_token: Runner JWT for MCP server identity
            timeout: Request timeout in seconds
        """
        self._enclave_url = enclave_url.rstrip("/")
        self._access_token = access_token
        self._dpop_key = dpop_key
        self._runner_token = runner_token
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

        dispatch_url = f"{self._enclave_url}/dispatch"

        # Build headers
        headers = {"Content-Type": "application/json"}

        # Add runner identity
        if self._runner_token:
            headers["X-Runner-Token"] = self._runner_token

        # Add DPoP authorization
        if self._dpop_key is not None:
            headers["Authorization"] = f"DPoP {self._access_token}"
            headers["DPoP"] = self._generate_dpop_proof(dispatch_url, "POST")
        else:
            headers["Authorization"] = f"Bearer {self._access_token}"

        # Build wire format body
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

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(dispatch_url, json=body, headers=headers)

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

            # Enclave returns DispatchResponse format
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
                return DispatchResponse.fail(
                    DispatchErrorCode(error_data.get("code", "downstream_unreachable")),
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

        import hashlib
        import json
        import time
        import uuid

        import jwt

        # Extract public key as JWK
        public_key = self._dpop_key.public_key()
        public_numbers = public_key.public_numbers()

        def b64url_encode(data: bytes) -> str:
            import base64

            return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

        x_bytes = public_numbers.x.to_bytes(32, byteorder="big")
        y_bytes = public_numbers.y.to_bytes(32, byteorder="big")

        jwk = {"kty": "EC", "crv": "P-256", "x": b64url_encode(x_bytes), "y": b64url_encode(y_bytes)}

        header = {"typ": "dpop+jwt", "alg": "ES256", "jwk": jwk}

        # Compute ath (access token hash)
        ath = b64url_encode(hashlib.sha256(self._access_token.encode()).digest())

        payload = {"jti": str(uuid.uuid4()), "htm": method, "htu": url, "iat": int(time.time()), "ath": ath}

        return jwt.encode(payload, self._dpop_key, algorithm="ES256", headers=header)


def create_dispatch_backend_from_env() -> DispatchBackend:
    """Create dispatch backend from environment variables.

    If DEDALUS_DISPATCH_URL is set, returns EnclaveDispatchBackend configured
    for Dedalus Cloud. Otherwise returns DirectDispatchBackend for OSS mode.

    Environment variables (Dedalus Cloud):
        DEDALUS_DISPATCH_URL: Dispatch Gateway URL (internal, not public)
        DEDALUS_RUNNER_TOKEN: Runner JWT minted by control plane at deploy
        DEDALUS_ACCESS_TOKEN: User's DPoP-bound access token (set per-request)

    Returns:
        Configured dispatch backend
    """
    import os

    dispatch_url = os.getenv("DEDALUS_DISPATCH_URL")

    if dispatch_url:
        runner_token = os.getenv("DEDALUS_RUNNER_TOKEN")
        # Access token and DPoP key are typically set per-request, not at init
        # This factory is for the runner identity; user auth is added later
        return EnclaveDispatchBackend(
            enclave_url=dispatch_url,
            access_token="",  # Set per-request via context
            runner_token=runner_token,
        )
    else:
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
