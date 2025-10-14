# OpenMCP Authorization Integration (Design Draft)

## Goals

- Support the HTTP authorization flow described in `docs/mcp/core/authorization`, ahead of the
  central Authorization Server (AS) going live at `https://as.dedaluslabs.ai`.
- Allow MCP servers built with OpenMCP to protect HTTP endpoints via OAuth 2.1 access tokens while
  remaining backward-compatible with unauthenticated deployments.
- Equip MCP clients to discover authorization requirements, register dynamically when needed, obtain
  tokens (PKCE + resource indicators), and attach them to subsequent requests.
- Keep the design modular so that downstream products can plug in alternative AS implementations or
  additional policy/guardrail layers.

## Non-goals

- Implement the AS itself; we assume an OAuth-compliant AS is available at
  `https://as.dedaluslabs.ai`.
- Support STDIO authorization (docs explicitly steer STDIO transports toward environment-driven
  credentials).
- Build UI/UX around login flows; downstream apps remain responsible for interactive consent screens.

## Overview

The design introduces opt-in authorization for the Streamable HTTP transport. When enabled:

1. The server advertises protected-resource metadata and enforces bearer tokens on incoming requests.
2. Clients detect `401` responses, discover the AS, optionally register dynamically, perform the OAuth
   authorization code with PKCE flow, and cache tokens.
3. Tokens are presented on every HTTP request via the `Authorization: Bearer` header, and the server
   validates and scopes them per the `resource` indicator.

We retain the ability to run in open mode (no auth) by toggling configuration.

## Server Components

### Configuration

Extend `MCPServer` to accept an optional `authorization` configuration block:

```python
AuthorizationConfig(
    enabled=True,
    metadata_url="https://openmcp.example.com/.well-known/oauth-protected-resource",
    required_scopes=["mcp:read", "mcp:write"],
    cache_ttl=300,
)
```

Defaults keep authorization disabled for existing deployments. When enabled the server:

- Generates and serves protected-resource metadata (RFC9728) under
  `/.well-known/oauth-protected-resource` or a configured path.
- Advertises the AS URL(s) (initially `https://as.dedaluslabs.ai`) and supported scopes/audience.
- Issues `401 Unauthorized` responses with a `WWW-Authenticate` header that includes the metadata URL.

### Token Validation

Streamable HTTP transport middleware will:

1. Extract and validate the `Authorization` header.
2. Call an `AuthorizationProvider` abstraction that can:
   - Fetch and cache JWKS or token introspection endpoints.
   - Validate signatures/expiration (`exp`, `aud`, `iss`), requiring the `resource` indicator to match
     the canonical server URI.
   - Enforce required scopes.
3. Reject invalid/missing tokens with `401` + proper `WWW-Authenticate` challenges.

We avoid embedding AS-specific logic by defining an interface:

```python
class AuthorizationProvider(Protocol):
    async def validate(self, token: str) -> AuthorizationContext:
        ...
```

The default implementation queries `as.dedaluslabs.ai` using OAuth metadata/jwks URIs. Future or custom
providers can extend this hook.

### Metadata Serving

A new handler exposes resource metadata using the OpenMCP transport stack. It will be registered
alongside other HTTP routes and independent of application logic. Metadata includes:

- `resource`: canonical URI of the server (auto-derived from runtime config).
- `authorization_servers`: list of AS endpoints.
- `scopes_supported`, `response_types_supported`, etc.

### Request Context

On successful validation we attach the decoded token claims to the request context (e.g., via
`request_ctx` metadata) so tool/resource handlers can optionally inspect user identity or scopes.

## Client Components

### Capability & Config

`MCPClient` gains optional authorization settings:

```python
ClientAuthorizationConfig(
    enabled=True,
    token_store=TokenStore(...),
    client_registration=DynamicRegistrationConfig(...),
)
```

When enabled the client pipeline will:

1. Detect `401` responses with `WWW-Authenticate` headers. Parse the protected-resource metadata URI.
2. Fetch and validate resource metadata, then AS metadata (RFC8414).
3. Optionally perform dynamic client registration (RFC7591) if a client ID is not already cached.
4. Run the authorization code with PKCE flow using the host application’s redirect URL. The design will
   expose hooks so apps can open a browser and capture the callback.
5. Persist access/refresh tokens in the provided `TokenStore` abstraction (memory or disk).
6. Attach `Authorization: Bearer <token>` and `MCP-Protocol-Version` headers to subsequent HTTP requests.

The client also uses the `resource` parameter (canonical server URI) during both the authorization and
  token exchange (RFC8707).

### Token Refresh

Implement automatic refresh with the refresh token grants exposed by the AS. The `TokenStore` tracks
expiry and refresh attempts, with exponential backoff and failure counters.

### Error Handling

If token acquisition fails, raise a structured error (e.g., `AuthorizationError`) so hosting apps can
surface UX to the user. For non-HTTP transports nothing changes.

## Shared Utilities

- JWKS caching helper with TTL and background refresh.
- URL helpers to compute canonical resource URIs.
- Pluggable storage abstraction (env var fallback, encrypted file store, in-memory for testing).
- CLI warnings/logging when authorization is required but config missing.

## Sequencing Plan

1. Land this design doc and gather feedback.
2. Implement server-side metadata + validation (feature-flagged).
3. Update Streamable HTTP transport to enforce tokens when enabled; add tests.
4. Extend `MCPClient` with discovery/registration/token management (mocked AS for tests).
5. Document configuration (`docs/openmcp/authorization.md`) and add integration examples.
6. Wire in the real AS endpoint when available; end-to-end smoke test using staging credentials.

## Open Questions

- How will hosted products capture OAuth redirect callbacks? (Likely per-app configuration; we expose a
  hook or callback interface.)
- Do we require mTLS or DPoP support from the AS? (Out of scope initially; rely on HTTPS + token
  claims.)
- Should we expose a lightweight policy interface so server authors can map scopes to tool/resource
  availability? (Nice-to-have once core flow is stable.)

## Risks

- AS downtime could block requests. We mitigate by caching validated tokens until expiry and allowing a
  “fail-open” optional mode for development.
- Clock skew can cause token validation failures; include leeway and log diagnostics.
- Dynamic registration may be disabled on the AS; clients must gracefully handle manual credential
  provisioning.

