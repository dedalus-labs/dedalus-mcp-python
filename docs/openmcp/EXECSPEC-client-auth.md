# EXECSPEC: Client-Side Auth — **COMPLETE**

## Goal

Provide transport-level auth injection for connecting to protected MCP servers. Support both DPoP (RFC 9449) for sender-constrained tokens and simple Bearer tokens.

**Primary API:**
```python
from dedalus_mcp.client import MCPClient, DPoPAuth

# DPoP auth (for Dedalus services)
auth = DPoPAuth(access_token="eyJ...", dpop_key=ec_private_key)
client = await MCPClient.connect("https://mcp.example.com/mcp", auth=auth)

# Bearer auth (for standard OAuth)
auth = BearerAuth(access_token="eyJ...")
client = await MCPClient.connect("https://mcp.example.com/mcp", auth=auth)
```

## Design Principles

1. **httpx.Auth interface** — Leverage existing httpx auth infrastructure rather than reinventing.

2. **Per-request proof generation** — DPoP proofs must be fresh for each request (unique `jti`, current `iat`, matching `htm`/`htu`).

3. **Token/nonce mutability** — Support updating access token (after refresh) and nonce (from server response) without recreating auth handler.

4. **Transport-level only** — OAuth flow orchestration (discovery, PKCE, token refresh) is user's responsibility. We provide the injection mechanism.

## Architecture

```
dedalus_mcp.client.auth
├── DPoPAuth(httpx.Auth)
│   ├── __init__(access_token, dpop_key, nonce?)
│   ├── auth_flow(request) -> Generator[Request, Response, None]
│   ├── set_access_token(token)
│   ├── set_nonce(nonce)
│   └── thumbprint -> str
├── BearerAuth(httpx.Auth)
│   ├── __init__(access_token)
│   ├── auth_flow(request)
│   └── set_access_token(token)
└── generate_dpop_proof(key, method, url, token?, nonce?) -> str
```

## Wire Format

DPoP auth injects two headers per RFC 9449 §7.1:
```http
Authorization: DPoP {access_token}
DPoP: {proof_jwt}
```

The proof JWT contains:
- `jti`: Unique per request (UUIDv4)
- `htm`: HTTP method (uppercase)
- `htu`: Target URI without query/fragment
- `iat`: Current Unix timestamp
- `ath`: SHA256 hash of access token (base64url)
- `nonce`: Server-provided nonce (optional)

## Invariants — **ALL VERIFIED**

### Phase 1: DPoP Proof Generation
- [x] `generate_dpop_proof()` creates valid JWT with correct header (`typ`, `alg`, `jwk`)
- [x] `htm` matches HTTP method (uppercased)
- [x] `htu` strips query and fragment per RFC 9449 §4.2
- [x] `jti` is unique per call
- [x] `iat` is current timestamp
- [x] `ath` included when access_token provided
- [x] `nonce` included when provided
- [x] Signature verifies with embedded JWK

### Phase 2: DPoPAuth Handler
- [x] Injects `Authorization: DPoP {token}` header
- [x] Injects `DPoP: {proof}` header with fresh proof per request
- [x] Proof includes `ath` for the access token
- [x] `set_nonce()` updates subsequent proofs
- [x] `set_access_token()` updates subsequent requests
- [x] `thumbprint` property returns JWK thumbprint

### Phase 3: BearerAuth Handler
- [x] Injects `Authorization: Bearer {token}` header
- [x] `set_access_token()` updates subsequent requests

### Phase 4: Integration
- [x] Works with `httpx.AsyncClient` transport
- [x] `MCPClient.connect()` accepts `auth` parameter

## Progress

Phase 1: DPoP Proof Generation — **COMPLETE**
- [x] Test: `test_proof_is_valid_jwt`
- [x] Test: `test_proof_has_correct_header`
- [x] Test: `test_proof_htm_matches_method`
- [x] Test: `test_proof_htu_strips_query_and_fragment`
- [x] Test: `test_proof_includes_ath_when_token_provided`
- [x] Test: `test_proof_excludes_ath_when_no_token`
- [x] Test: `test_proof_includes_nonce_when_provided`
- [x] Test: `test_proof_jti_is_unique`
- [x] Test: `test_proof_iat_is_current`
- [x] Test: `test_proof_signature_verifies`
- [x] Implementation: `generate_dpop_proof()` in `auth.py`

Phase 2: DPoPAuth Handler — **COMPLETE**
- [x] Test: `test_auth_adds_authorization_header`
- [x] Test: `test_auth_adds_dpop_header`
- [x] Test: `test_auth_proof_includes_ath`
- [x] Test: `test_auth_proof_includes_nonce`
- [x] Test: `test_set_nonce_updates_proof`
- [x] Test: `test_set_access_token_updates_auth`
- [x] Test: `test_thumbprint_property`
- [x] Implementation: `DPoPAuth` class

Phase 3: BearerAuth Handler — **COMPLETE**
- [x] Test: `test_auth_adds_bearer_header`
- [x] Test: `test_set_access_token_updates_header`
- [x] Implementation: `BearerAuth` class

Phase 4: Integration — **COMPLETE**
- [x] Test: `test_dpop_auth_with_async_client`
- [x] Implementation: `auth` parameter on `MCPClient.connect()`

## Files Modified

- `src/dedalus_mcp/client/auth.py` — **NEW**: DPoPAuth, BearerAuth, generate_dpop_proof
- `src/dedalus_mcp/client/core.py` — Added `auth` parameter to `connect()`
- `src/dedalus_mcp/client/__init__.py` — Export auth classes
- `tests/test_client_auth.py` — **NEW**: 23 tests

## Integration with Dedalus Services

| Component | Wire Format | Status |
|-----------|-------------|--------|
| Dispatch Gateway | `Authorization: DPoP` + `DPoP:` headers | ✅ Compatible |
| Dedalus MCP AS | Token with `cnf.jkt` claim | ✅ Compatible (user obtains token) |
| MCP Server | Standard Bearer or DPoP | ✅ Both supported |

## Non-Goals

- OAuth flow orchestration (discovery, PKCE, etc.) — user's responsibility
- Token refresh automation — user calls `set_access_token()`
- Token storage — user's responsibility

## References

- RFC 9449: OAuth 2.0 Demonstrating Proof of Possession (DPoP)
- RFC 7638: JSON Web Key (JWK) Thumbprint
- `/dcs/apps/dedalus_mcp_as/dpop/dpop.go` — Go implementation (validation)
- `/dcs/apps/enclave/dispatch-gateway/src/handlers.rs` — Gateway validation
- `/auth-specs/auth-specs-notion.md` — Dedalus auth architecture

