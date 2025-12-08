# DPoP Authentication

DPoP (RFC 9449) binds access tokens to a keypair. Stolen tokens are useless without the private key.

## Why DPoP

Bearer tokens are bearer instruments. Steal one from a log, storage, or network capture and you have full access until expiry. DPoP fixes this by requiring a fresh cryptographic proof with each request, signed by a key only the legitimate client holds.

Attack vectors addressed: token leakage via logs, storage compromise, network interception, confused deputy attacks where a malicious server replays your token elsewhere.

## Client Usage

```python
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.backends import default_backend
from dedalus_mcp.client import MCPClient, DPoPAuth

# Generate or load your key (P-256/ES256)
dpop_key = ec.generate_private_key(ec.SECP256R1(), default_backend())

# Obtain token from AS with DPoP binding (your OAuth flow)
# The AS embeds your key's thumbprint in the token as cnf.jkt
access_token = "eyJ..."

# Create auth handler
auth = DPoPAuth(access_token=access_token, dpop_key=dpop_key)

# Connect - headers injected automatically per-request
client = await MCPClient.connect("https://mcp.example.com/mcp", auth=auth)
tools = await client.list_tools()
await client.close()
```

Each request includes two headers:

```http
Authorization: DPoP eyJ...
DPoP: eyJhbGciOiJFUzI1NiIsInR5cCI6ImRwb3Arand0IiwiandrIjp7...}}...
```

The proof JWT contains: unique `jti` (replay prevention), `htm` (HTTP method), `htu` (target URL), `iat` (timestamp), `ath` (token hash).

## Token Refresh

Update the token without recreating the auth handler:

```python
auth.set_access_token(new_token)
```

## Server Nonces

If the server returns a `DPoP-Nonce` header in a 401 response (RFC 9449 §8):

```python
auth.set_nonce(nonce_from_response)
# Retry request
```

## Standalone Proof Generation

For custom integrations:

```python
from dedalus_mcp.client.auth import generate_dpop_proof

proof = generate_dpop_proof(
    dpop_key=private_key,
    method="POST",
    url="https://api.example.com/endpoint",
    access_token="eyJ...",  # Optional: includes ath claim
    nonce="server_nonce",   # Optional: if server requires
)
```

## Server-Side Validation

The `DPoPValidator` validates incoming proofs:

```python
from dedalus_mcp.server.services.dpop import DPoPValidator, DPoPValidatorConfig

config = DPoPValidatorConfig(leeway=60, jti_cache_ttl=120)
validator = DPoPValidator(config)

result = validator.validate_proof(
    proof=dpop_header,
    method="POST",
    url="https://mcp.example.com/messages",
    expected_thumbprint=token_cnf_jkt,  # From JWT cnf.jkt claim
    access_token=access_token,          # Validates ath claim
)
# result.jti, result.htm, result.htu available
```

Validation checks: signature, `typ`/`alg` headers, JWK presence (no private key material), `htm`/`htu` match, `iat` freshness, `jti` uniqueness, `ath` match, thumbprint binding.

## Integration Points

| Component | Role |
|-----------|------|
| `dedalus_mcp.client.auth.DPoPAuth` | Client-side proof generation |
| `dedalus_mcp.server.services.dpop.DPoPValidator` | Server-side proof validation |
| `apps/openmcp_as/dpop/dpop.go` | AS validation (Go) |

## What DPoP Does Not Protect

API keys. DPoP binds tokens, not the credentials used to obtain them. An attacker who steals your API key can generate their own DPoP keypair, exchange the key for a token bound to their key, and use the system. Protect API keys with rotation, monitoring, and secure storage.

## References

- [RFC 9449: OAuth 2.0 DPoP](https://datatracker.ietf.org/doc/html/rfc9449)
- [RFC 7638: JWK Thumbprint](https://datatracker.ietf.org/doc/html/rfc7638)
- [Example: examples/client/dpop_auth.py](../../examples/client/dpop_auth.py)
- [Tests: tests/test_client_auth.py, tests/test_dpop.py](../../tests/)
