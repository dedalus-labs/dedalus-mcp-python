# ==============================================================================
#                  © 2025 Dedalus Labs, Inc. and affiliates
#                            Licensed under MIT
#               github.com/dedalus-labs/openmcp-python/LICENSE
# ==============================================================================

"""Binary resources with base64 encoding.

Demonstrates serving binary content (images, certificates, archives) via MCP.
Framework auto-wraps bytes return values in BlobResourceContents with base64
encoding. Useful for non-text data that clients need to retrieve.

Pattern:
- Resource function returns bytes
- Framework wraps in BlobResourceContents(blob=base64_string)
- mime_type identifies binary format (image/png, application/pdf)
- Clients decode base64 to recover original bytes

When to use:
- Images, logos, diagrams
- Certificates, keys (PEM/DER format)
- Archives, binary protocols
- Generated PDFs or media

Spec: https://modelcontextprotocol.io/specification/2025-06-18/server/resources
Usage: uv run python examples/resources/binary_resource.py
"""

from __future__ import annotations

import asyncio
import base64
import logging

from openmcp import MCPServer, resource

# Suppress logs for clean demo output
for logger_name in ("mcp", "httpx", "uvicorn", "uvicorn.access", "uvicorn.error"):
    logging.getLogger(logger_name).setLevel(logging.CRITICAL)

server = MCPServer("binary-resources")

with server.binding():

    @resource(
        uri="image://logo.png",
        name="Company Logo",
        description="PNG logo image",
        mime_type="image/png",
    )
    def company_logo() -> bytes:
        """Return binary image data.

        Resources returning bytes are automatically wrapped in BlobResourceContents
        with base64 encoding. This example generates a minimal 1x1 PNG.
        """
        # Minimal valid PNG: 1x1 transparent pixel
        # Real applications would load from disk or generate dynamic images
        png_data = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
        )
        return png_data

    @resource(
        uri="data://sample.bin",
        name="Binary Data",
        description="Raw binary payload",
        mime_type="application/octet-stream",
    )
    def binary_payload() -> bytes:
        """Arbitrary binary data as resource."""
        # Example: structured binary data (could be protobuf, msgpack, etc.)
        return bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])

    @resource(
        uri="file://cert.pem",
        name="Certificate",
        description="PEM-encoded certificate",
        mime_type="application/x-pem-file",
    )
    def certificate() -> bytes:
        """Certificate data as binary resource."""
        pem_content = b"""-----BEGIN CERTIFICATE-----
MIIBkTCB+wIJAKHHCgVZU5KpMA0GCSqGSIb3DQEBCwUAMBExDzANBgNVBAMMBnRl
c3RDQTAeFw0yNDAxMDEwMDAwMDBaFw0yNTAxMDEwMDAwMDBaMBExDzANBgNVBAMM
BnRlc3RDQTCBnzANBgkqhkiG9w0BAQEFAAOBjQAwgYkCgYEAwPPZ0r7lR3zlJGd7
-----END CERTIFICATE-----"""
        return pem_content


async def main() -> None:
    await server.serve(transport="streamable-http", verbose=False, log_level="critical")


if __name__ == "__main__":
    asyncio.run(main())
