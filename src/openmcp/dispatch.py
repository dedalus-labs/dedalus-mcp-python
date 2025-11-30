# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Dispatch backend for privileged operations.

This module provides the interface for tools to execute privileged operations
through connection handles. Two backend implementations are provided:

- `DirectDispatchBackend`: OSS mode - calls downstream APIs directly using
  credentials loaded from environment variables or local configuration.

- `EnclaveDispatchBackend`: Production mode - forwards requests to the
  Dedalus Enclave with DPoP-bound access tokens for secure credential isolation.

The dispatch flow:
1. Tool calls `ctx.dispatch(handle, intent, arguments)`
2. Connection gate validates handle against JWT's `ddls:connections` claim
3. Backend executes the operation (locally or via Enclave)
4. Result returned to tool

Example:
    >>> # In a tool function
    >>> async def create_github_issue(ctx: Context, title: str) -> dict:
    ...     result = await ctx.dispatch(
    ...         connection_handle="ddls:conn:01ABC-github",
    ...         intent="github:create_issue",
    ...         arguments={"title": title, "body": "Auto-created"},
    ...     )
    ...     return result.data

References:
    /dcs/apps/enclave/IMPLEMENTATION_SPEC.md (wire format)
"""

from __future__ import annotations

import re
from typing import Any, Callable, Protocol, runtime_checkable

from pydantic import BaseModel, Field, field_validator

from .utils import get_logger

_logger = get_logger("openmcp.dispatch")


# =============================================================================
# Data Models
# =============================================================================


class DispatchRequest(BaseModel):
    """Request to dispatch a privileged operation.

    Attributes:
        connection_handle: Identifier for the connection to use (e.g., "ddls:conn:01ABC-github")
        intent: Operation identifier (e.g., "github:create_issue")
        arguments: Operation-specific arguments
    """

    connection_handle: str = Field(..., min_length=1, description="Connection handle identifier")
    intent: str = Field(..., min_length=1, description="Operation intent identifier")
    arguments: dict[str, Any] = Field(default_factory=dict, description="Operation arguments")

    @field_validator("connection_handle")
    @classmethod
    def validate_handle_format(cls, v: str) -> str:
        """Validate connection handle format."""
        if not v.startswith("ddls:conn"):
            raise ValueError("connection_handle must start with 'ddls:conn'")
        return v


class DispatchResult(BaseModel):
    """Result of a dispatched operation.

    Attributes:
        success: Whether the operation succeeded
        data: Result data if successful
        error: Error message if failed
    """

    success: bool
    data: dict[str, Any] | None = None
    error: str | None = None


# =============================================================================
# Backend Protocol
# =============================================================================


@runtime_checkable
class DispatchBackend(Protocol):
    """Protocol for dispatch backend implementations.

    Backends handle the actual execution of privileged operations, either
    locally (DirectDispatchBackend) or via the Enclave (EnclaveDispatchBackend).
    """

    async def dispatch(self, request: DispatchRequest) -> DispatchResult:
        """Execute a privileged operation.

        Args:
            request: The dispatch request containing handle, intent, and arguments

        Returns:
            DispatchResult with success/failure and data/error
        """
        ...


# =============================================================================
# Direct Dispatch Backend (OSS Mode)
# =============================================================================


# Type for driver execute functions
DriverExecutor = Callable[[str, dict[str, Any]], Any]


class DirectDispatchBackend:
    """Dispatch backend for OSS mode with local credentials.

    This backend executes operations directly by delegating to registered
    drivers. Credentials are loaded from environment variables or local
    configuration rather than going through the Enclave.

    Useful for:
    - Local development without Enclave access
    - Self-hosted deployments with direct credential management
    - Testing and CI environments

    Example:
        >>> backend = DirectDispatchBackend()
        >>> backend.register_driver("github", github_driver.execute)
        >>> result = await backend.dispatch(request)
    """

    def __init__(self) -> None:
        self._drivers: dict[str, DriverExecutor] = {}

    def register_driver(self, provider: str, executor: DriverExecutor) -> None:
        """Register a driver for a provider.

        Args:
            provider: Provider identifier (e.g., "github", "slack")
            executor: Async function that executes intents for this provider
        """
        self._drivers[provider] = executor
        _logger.debug("driver registered", extra={"event": "dispatch.driver.registered", "provider": provider})

    async def dispatch(self, request: DispatchRequest) -> DispatchResult:
        """Execute operation using registered driver.

        Args:
            request: Dispatch request

        Returns:
            DispatchResult with operation outcome
        """
        # Extract provider from intent (e.g., "github:create_issue" -> "github")
        provider = self._extract_provider(request.intent)

        if provider not in self._drivers:
            available = list(self._drivers.keys())
            error_msg = f"no driver registered for provider '{provider}'. Available: {available}"
            _logger.warning(
                "dispatch failed - unknown driver",
                extra={"event": "dispatch.driver.unknown", "provider": provider, "intent": request.intent},
            )
            return DispatchResult(success=False, error=error_msg)

        driver = self._drivers[provider]

        try:
            # Call the driver
            import asyncio
            import inspect

            if inspect.iscoroutinefunction(driver):
                result = await driver(request.intent, request.arguments)
            else:
                # Run sync driver in thread pool
                result = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: driver(request.intent, request.arguments)
                )

            _logger.debug(
                "dispatch succeeded",
                extra={"event": "dispatch.success", "provider": provider, "intent": request.intent},
            )

            return DispatchResult(success=True, data=result if isinstance(result, dict) else {"result": result})

        except Exception as e:
            error_msg = f"driver execution failed: {e}"
            _logger.warning(
                "dispatch failed - driver exception",
                extra={
                    "event": "dispatch.driver.error",
                    "provider": provider,
                    "intent": request.intent,
                    "error": str(e),
                },
            )
            return DispatchResult(success=False, error=error_msg)

    @staticmethod
    def _extract_provider(intent: str) -> str:
        """Extract provider from intent string."""
        if ":" in intent:
            return intent.split(":")[0]
        return intent


# =============================================================================
# Enclave Dispatch Backend
# =============================================================================


class EnclaveDispatchBackend:
    """Dispatch backend that forwards to the Dedalus Enclave.

    This backend sends operations to the Enclave with DPoP-bound access tokens.
    The Enclave securely manages credentials and executes operations on behalf
    of the MCP server.

    Wire format (POST /dispatch):
        Authorization: DPoP {access_token}
        DPoP: {dpop_proof}
        Content-Type: application/json

        {
            "connection_handle": "ddls:conn:01ABC-github",
            "intent": "github:create_issue",
            "arguments": {...}
        }

    Example:
        >>> backend = EnclaveDispatchBackend(
        ...     enclave_url="https://enclave.dedalus.cloud",
        ...     access_token=token,
        ...     dpop_key=key,  # ES256 private key for DPoP proofs
        ... )
        >>> result = await backend.dispatch(request)
    """

    def __init__(self, enclave_url: str, access_token: str, dpop_key: Any | None = None, timeout: float = 30.0) -> None:
        """Initialize enclave backend.

        Args:
            enclave_url: Base URL of the Enclave (e.g., "https://enclave.dedalus.cloud")
            access_token: DPoP-bound access token
            dpop_key: ES256 private key for DPoP proof generation
            timeout: Request timeout in seconds
        """
        self._enclave_url = enclave_url.rstrip("/")
        self._access_token = access_token
        self._dpop_key = dpop_key
        self._timeout = timeout

    async def dispatch(self, request: DispatchRequest) -> DispatchResult:
        """Forward operation to Enclave.

        Args:
            request: Dispatch request

        Returns:
            DispatchResult with Enclave response
        """
        try:
            import httpx
        except ImportError:
            return DispatchResult(success=False, error="httpx not installed; required for Enclave dispatch")

        dispatch_url = f"{self._enclave_url}/dispatch"

        # Build headers
        headers = {"Content-Type": "application/json"}

        # Add DPoP authorization
        if self._dpop_key is not None:
            headers["Authorization"] = f"DPoP {self._access_token}"
            headers["DPoP"] = self._generate_dpop_proof(dispatch_url, "POST")
        else:
            # Fallback to bearer (not recommended in production)
            headers["Authorization"] = f"Bearer {self._access_token}"

        # Build request body
        body = {
            "connection_handle": request.connection_handle,
            "intent": request.intent,
            "arguments": request.arguments,
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(dispatch_url, json=body, headers=headers)

            if response.status_code == 401:
                return DispatchResult(success=False, error=f"authentication failed (401): {response.text}")

            if response.status_code == 403:
                return DispatchResult(success=False, error=f"authorization failed (403): {response.text}")

            if response.status_code >= 400:
                return DispatchResult(success=False, error=f"enclave error ({response.status_code}): {response.text}")

            data = response.json()

            # Enclave returns {success: bool, data?: {...}, error?: string}
            return DispatchResult(success=data.get("success", True), data=data.get("data"), error=data.get("error"))

        except httpx.TimeoutException:
            return DispatchResult(success=False, error="enclave request timed out")
        except httpx.RequestError as e:
            return DispatchResult(success=False, error=f"enclave request failed: {e}")
        except Exception as e:
            _logger.exception(
                "unexpected enclave dispatch error", extra={"event": "dispatch.enclave.error", "error": str(e)}
            )
            return DispatchResult(success=False, error=f"unexpected error: {e}")

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


__all__ = ["DispatchRequest", "DispatchResult", "DispatchBackend", "DirectDispatchBackend", "EnclaveDispatchBackend"]
