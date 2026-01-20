# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Complete DPoP OAuth flow for MCP clients.

Demonstrates the full authorization code + PKCE + DPoP flow:
1. Generate DPoP keypair
2. Discover AS metadata
3. Authorization code request with dpop_jkt
4. Token exchange with DPoP proof
5. Connect to MCP server with DPoP-bound token

This is a reference implementation. Production code should use a proper
OAuth library and secure key storage.

Usage:
    # Requires AS at https://as.example.com and MCP server
    export MCP_SERVER_URL=https://mcp.example.com/mcp
    export AS_URL=https://as.example.com
    uv run python examples/auth/06_dpop_flow/client.py
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import secrets
from urllib.parse import urlencode

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePrivateKey
import httpx

from dedalus_mcp.client import DPoPAuth
from dedalus_mcp.auth.dpop import generate_dpop_proof


def b64url(data: bytes) -> str:
    """Base64url encode without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def compute_thumbprint(public_key: ec.EllipticCurvePublicKey) -> str:
    """Compute JWK thumbprint per RFC 7638."""
    nums = public_key.public_numbers()
    x = b64url(nums.x.to_bytes(32, "big"))
    y = b64url(nums.y.to_bytes(32, "big"))
    canonical = json.dumps({"crv": "P-256", "kty": "EC", "x": x, "y": y}, separators=(",", ":"), sort_keys=True)
    return b64url(hashlib.sha256(canonical.encode()).digest())


class DPoPOAuthClient:
    """OAuth 2.1 client with DPoP support."""

    def __init__(self, as_url: str, client_id: str, redirect_uri: str) -> None:
        self.as_url = as_url.rstrip("/")
        self.client_id = client_id
        self.redirect_uri = redirect_uri

        # Generate DPoP keypair - in production, persist securely
        self.dpop_key: EllipticCurvePrivateKey = ec.generate_private_key(ec.SECP256R1(), default_backend())
        self.dpop_jkt = compute_thumbprint(self.dpop_key.public_key())

        self._http = httpx.AsyncClient()
        self._as_metadata: dict | None = None

    async def close(self) -> None:
        await self._http.aclose()

    async def discover_as(self) -> dict:
        """Fetch AS metadata (RFC 8414)."""
        if self._as_metadata:
            return self._as_metadata

        # Try OAuth 2.0 AS metadata first, fall back to OIDC
        for path in ["/.well-known/oauth-authorization-server", "/.well-known/openid-configuration"]:
            resp = await self._http.get(f"{self.as_url}{path}")
            if resp.status_code == 200:
                self._as_metadata = resp.json()
                return self._as_metadata

        raise RuntimeError(f"Could not discover AS metadata at {self.as_url}")

    def build_authorization_url(self, resource: str, scope: str = "openid") -> tuple[str, str, str]:
        """Build authorization URL with PKCE and DPoP binding.

        Returns (url, code_verifier, state).
        """
        # PKCE
        code_verifier = secrets.token_urlsafe(64)[:128]
        code_challenge = b64url(hashlib.sha256(code_verifier.encode()).digest())

        state = secrets.token_urlsafe(32)

        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": scope,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "resource": resource,
            "dpop_jkt": self.dpop_jkt,  # Bind DPoP key to authorization
        }

        # Use discovered authorize endpoint or default
        authorize_endpoint = self.as_url + "/authorize"
        if self._as_metadata:
            authorize_endpoint = self._as_metadata.get("authorization_endpoint", authorize_endpoint)

        return f"{authorize_endpoint}?{urlencode(params)}", code_verifier, state

    async def exchange_code(self, code: str, code_verifier: str, resource: str) -> dict:
        """Exchange authorization code for tokens with DPoP proof."""
        token_endpoint = self.as_url + "/token"
        if self._as_metadata:
            token_endpoint = self._as_metadata.get("token_endpoint", token_endpoint)

        # Generate DPoP proof for token endpoint
        dpop_proof = generate_dpop_proof(dpop_key=self.dpop_key, method="POST", url=token_endpoint)

        resp = await self._http.post(
            token_endpoint,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.redirect_uri,
                "client_id": self.client_id,
                "code_verifier": code_verifier,
                "resource": resource,
            },
            headers={"DPoP": dpop_proof},
        )

        if resp.status_code != 200:
            raise RuntimeError(f"Token exchange failed: {resp.status_code} {resp.text}")

        tokens = resp.json()

        # Verify token_type is DPoP
        if tokens.get("token_type", "").lower() != "dpop":
            print(f"Warning: Expected token_type=DPoP, got {tokens.get('token_type')}")

        return tokens

    async def refresh_token(self, refresh_token: str, resource: str) -> dict:
        """Refresh access token with DPoP proof."""
        token_endpoint = self.as_url + "/token"
        if self._as_metadata:
            token_endpoint = self._as_metadata.get("token_endpoint", token_endpoint)

        dpop_proof = generate_dpop_proof(dpop_key=self.dpop_key, method="POST", url=token_endpoint)

        resp = await self._http.post(
            token_endpoint,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": self.client_id,
                "resource": resource,
            },
            headers={"DPoP": dpop_proof},
        )

        if resp.status_code != 200:
            raise RuntimeError(f"Token refresh failed: {resp.status_code} {resp.text}")

        return resp.json()


async def main() -> None:
    mcp_url = os.environ.get("MCP_SERVER_URL", "https://mcp.example.com/mcp")
    as_url = os.environ.get("AS_URL", "https://as.example.com")
    client_id = os.environ.get("CLIENT_ID", "example-mcp-client")
    redirect_uri = os.environ.get("REDIRECT_URI", "http://localhost:3000/callback")

    print("=== DPoP OAuth Flow Demo ===\n")

    oauth = DPoPOAuthClient(as_url, client_id, redirect_uri)

    try:
        # Step 1: Discover AS
        print(f"1. Discovering AS at {as_url}...")
        try:
            metadata = await oauth.discover_as()
            print(f"   Found: {metadata.get('issuer', 'unknown issuer')}")
        except Exception as e:
            print(f"   Skipping discovery (demo mode): {e}")

        # Step 2: Build authorization URL
        print("\n2. Building authorization URL with DPoP binding...")
        auth_url, code_verifier, state = oauth.build_authorization_url(resource=mcp_url)
        print(f"   DPoP JKT: {oauth.dpop_jkt[:20]}...")
        print("   Open this URL to authorize:")
        print(f"   {auth_url[:100]}...")

        # Step 3: Simulate callback (in real app, user completes OAuth in browser)
        print("\n3. Waiting for authorization code...")
        print("   (In production: user authorizes in browser, callback receives code)")

        # For demo, we'll just show what would happen
        demo_code = "demo_authorization_code"
        print(f"   Using demo code: {demo_code}")

        # Step 4: Exchange code for tokens
        print("\n4. Exchanging code for DPoP-bound tokens...")
        print("   (Skipping actual exchange in demo mode)")

        # In real flow:
        # tokens = await oauth.exchange_code(code, code_verifier, mcp_url)
        # access_token = tokens["access_token"]

        # Step 5: Connect to MCP with DPoP auth
        print("\n5. Connecting to MCP server with DPoP auth...")

        # Demo: create auth handler (would use real token in production)
        auth = DPoPAuth(access_token="demo_access_token", dpop_key=oauth.dpop_key)
        print(f"   Auth thumbprint: {auth.thumbprint[:20]}...")

        print("\n   To complete the flow with a real server:")
        print("   - Set MCP_SERVER_URL, AS_URL, CLIENT_ID, REDIRECT_URI")
        print("   - Complete the OAuth flow in browser")
        print("   - The client will connect with DPoP-bound tokens")

        # Uncomment to actually connect:
        # client = await MCPClient.connect(mcp_url, auth=auth)
        # tools = await client.list_tools()
        # print(f"   Connected! Tools: {[t.name for t in tools.tools]}")
        # await client.close()

    finally:
        await oauth.close()

    print("\n=== Demo Complete ===")


if __name__ == "__main__":
    asyncio.run(main())
