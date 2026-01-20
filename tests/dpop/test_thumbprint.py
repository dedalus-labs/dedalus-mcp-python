# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Tests for JWK thumbprint computation per RFC 7638.

These tests verify that thumbprint computation follows RFC 7638:
- Canonical JSON representation (sorted keys, no whitespace)
- Correct required members for each key type
- SHA-256 hash with base64url encoding
"""

from __future__ import annotations

import hashlib
import json

import pytest

from dedalus_mcp.auth.dpop import compute_access_token_hash, compute_jwk_thumbprint
from dedalus_mcp.auth.dpop.thumbprint import b64url_decode, b64url_encode


class TestB64UrlEncode:
    """Tests for base64url encoding/decoding."""

    def test_encode_no_padding(self):
        """Should encode without padding."""
        result = b64url_encode(b"test")
        assert "=" not in result

    def test_roundtrip(self):
        """Encode then decode should return original."""
        data = b"hello world"
        encoded = b64url_encode(data)
        decoded = b64url_decode(encoded)
        assert decoded == data

    def test_url_safe_characters(self):
        """Should use URL-safe characters (- and _ instead of + and /)."""
        # Data that would produce + and / in standard base64
        data = bytes([0b11111011, 0b11101111])
        encoded = b64url_encode(data)
        assert "+" not in encoded
        assert "/" not in encoded


class TestComputeJwkThumbprint:
    """Tests for RFC 7638 JWK thumbprint computation."""

    def test_ec_p256_thumbprint(self, es256_keypair):
        """EC P-256 key thumbprint should follow RFC 7638."""
        public_key = es256_keypair.public_key()
        public_numbers = public_key.public_numbers()

        x_bytes = public_numbers.x.to_bytes(32, byteorder="big")
        y_bytes = public_numbers.y.to_bytes(32, byteorder="big")

        jwk = {"kty": "EC", "crv": "P-256", "x": b64url_encode(x_bytes), "y": b64url_encode(y_bytes)}

        thumbprint = compute_jwk_thumbprint(jwk)

        # Should be 43 chars (256 bits / 6 bits per char = 42.67, rounded up)
        assert len(thumbprint) == 43
        assert "=" not in thumbprint

    def test_canonical_json_order(self, es256_keypair):
        """Thumbprint should use lexicographically sorted keys."""
        public_key = es256_keypair.public_key()
        public_numbers = public_key.public_numbers()

        x = b64url_encode(public_numbers.x.to_bytes(32, byteorder="big"))
        y = b64url_encode(public_numbers.y.to_bytes(32, byteorder="big"))

        # JWK with keys in different order
        jwk1 = {"kty": "EC", "crv": "P-256", "x": x, "y": y}
        jwk2 = {"y": y, "x": x, "kty": "EC", "crv": "P-256"}

        # Should produce same thumbprint regardless of input order
        assert compute_jwk_thumbprint(jwk1) == compute_jwk_thumbprint(jwk2)

    def test_canonical_json_format(self, es256_keypair):
        """Thumbprint should use correct canonical JSON format."""
        public_key = es256_keypair.public_key()
        public_numbers = public_key.public_numbers()

        x = b64url_encode(public_numbers.x.to_bytes(32, byteorder="big"))
        y = b64url_encode(public_numbers.y.to_bytes(32, byteorder="big"))

        jwk = {"kty": "EC", "crv": "P-256", "x": x, "y": y}

        # Manually compute expected thumbprint
        # Order for EC: crv, kty, x, y (alphabetical)
        canonical = json.dumps({"crv": "P-256", "kty": "EC", "x": x, "y": y}, separators=(",", ":"), sort_keys=True)
        expected = b64url_encode(hashlib.sha256(canonical.encode()).digest())

        assert compute_jwk_thumbprint(jwk) == expected

    def test_extra_fields_ignored(self, es256_keypair):
        """Extra JWK fields should not affect thumbprint."""
        public_key = es256_keypair.public_key()
        public_numbers = public_key.public_numbers()

        x = b64url_encode(public_numbers.x.to_bytes(32, byteorder="big"))
        y = b64url_encode(public_numbers.y.to_bytes(32, byteorder="big"))

        jwk_minimal = {"kty": "EC", "crv": "P-256", "x": x, "y": y}
        jwk_with_extras = {"kty": "EC", "crv": "P-256", "x": x, "y": y, "kid": "key-id", "use": "sig", "alg": "ES256"}

        assert compute_jwk_thumbprint(jwk_minimal) == compute_jwk_thumbprint(jwk_with_extras)

    def test_unsupported_key_type_raises(self):
        """Unsupported key types should raise ValueError."""
        jwk = {"kty": "OKP", "crv": "Ed25519", "x": "base64data"}

        with pytest.raises(ValueError, match="unsupported key type"):
            compute_jwk_thumbprint(jwk)

    def test_different_keys_different_thumbprints(self, es256_keypair, es256_keypair_alt):
        """Different keys should produce different thumbprints."""
        public_key1 = es256_keypair.public_key()
        public_numbers1 = public_key1.public_numbers()
        jwk1 = {
            "kty": "EC",
            "crv": "P-256",
            "x": b64url_encode(public_numbers1.x.to_bytes(32, byteorder="big")),
            "y": b64url_encode(public_numbers1.y.to_bytes(32, byteorder="big")),
        }

        public_key2 = es256_keypair_alt.public_key()
        public_numbers2 = public_key2.public_numbers()
        jwk2 = {
            "kty": "EC",
            "crv": "P-256",
            "x": b64url_encode(public_numbers2.x.to_bytes(32, byteorder="big")),
            "y": b64url_encode(public_numbers2.y.to_bytes(32, byteorder="big")),
        }

        assert compute_jwk_thumbprint(jwk1) != compute_jwk_thumbprint(jwk2)


class TestComputeAccessTokenHash:
    """Tests for access token hash (ath claim) computation."""

    def test_sha256_hash(self):
        """Should compute SHA-256 hash."""
        token = "test-access-token"
        ath = compute_access_token_hash(token)

        # Manually compute expected
        expected = b64url_encode(hashlib.sha256(token.encode("ascii")).digest())
        assert ath == expected

    def test_base64url_encoded(self):
        """Result should be base64url encoded without padding."""
        token = "test-access-token"
        ath = compute_access_token_hash(token)

        assert "=" not in ath
        assert "+" not in ath
        assert "/" not in ath

    def test_correct_length(self):
        """SHA-256 base64url should be 43 characters."""
        token = "any-token"
        ath = compute_access_token_hash(token)
        assert len(ath) == 43

    def test_deterministic(self):
        """Same token should produce same hash."""
        token = "consistent-token"

        ath1 = compute_access_token_hash(token)
        ath2 = compute_access_token_hash(token)

        assert ath1 == ath2

    def test_different_tokens_different_hashes(self):
        """Different tokens should produce different hashes."""
        ath1 = compute_access_token_hash("token-one")
        ath2 = compute_access_token_hash("token-two")

        assert ath1 != ath2
