# Transports
Source: https://modelcontextprotocol.io/specification/2025-06-18/basic/transports



<div id="enable-section-numbers" />

<Info>**Protocol Revision**: 2025-06-18</Info>

MCP uses JSON-RPC to encode messages. JSON-RPC messages **MUST** be UTF-8 encoded.

The protocol currently defines two standard transport mechanisms for client-server
communication:

1. [stdio](stdio.md#stdio), communication over standard in and standard out
2. [Streamable HTTP](streamable-http.md#streamable-http)

Clients **SHOULD** support stdio whenever possible.

It is also possible for clients and servers to implement
[custom transports](custom-transports.md#custom-transports) in a pluggable fashion.
