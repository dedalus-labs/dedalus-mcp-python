# Glossary

MCP and related terminology used in this project.

## MCP Core Concepts

**MCP (Model Context Protocol)**
: A protocol for AI models to access external tools, resources, and prompts in a standardized way.

**MCP Server**
: A service that exposes tools, resources, and prompts via the MCP protocol. Built with Dedalus MCP.

**MCP Client**
: An application (typically an AI assistant) that connects to MCP servers to use their capabilities.

**Transport**
: The communication layer between client and server. Common transports: stdio, HTTP.

## Primitives

**Tool**
: A function the AI can invoke to perform actions. Has a name, description, and JSON schema for parameters.

**Resource**
: Data the AI can read. Identified by URI. Can be static or dynamic.

**Resource Template**
: A parameterized resource URI pattern (e.g., `file://{path}`). Allows dynamic resource generation.

**Prompt**
: A reusable message template with optional parameters. Helps structure AI interactions.

## Protocol Terms

**Capability**
: A feature the server declares support for (tools, resources, prompts, etc.).

**Initialize**
: The handshake between client and server. Exchanges capabilities and protocol version.

**Notification**
: A one-way message that doesn't expect a response.

**Request/Response**
: A message pair where the sender expects a reply.

**Progress**
: Optional reporting of long-running operation status.

## Server Concepts

**Context**
: Request-scoped state available to tool/resource handlers. Access via `get_context()`.

**Decorator**
: The `@tool`, `@resource`, `@prompt` syntax for registering handlers.

**Handler**
: A function that implements a tool, resource, or prompt.

**Service**
: Internal component managing a category of handlers (ToolService, ResourceService, etc.).

## Client Concepts

**Connection**
: An active link to an MCP server. Manages lifecycle and communication.

**Session**
: The period between initialize and disconnect. Maintains state.

**Sampling**
: Client capability to generate AI completions. Server can request this.

**Roots**
: Filesystem paths the client exposes to servers.

## Authorization Terms

**OAuth 2.1**
: The authorization protocol used for secure MCP connections.

**Bearer Token**
: A token included in requests to prove authorization.

**Scope**
: Permissions granted to a token (e.g., `tools:read`, `resources:write`).

## Framework Terms

**MCPServer**
: The main class for building MCP servers in Dedalus MCP.

**MCPClient**
: The main class for connecting to MCP servers.

**Pydantic**
: The validation library used for type-safe parameters and responses.

## See Also

- [MCP Specification](https://spec.modelcontextprotocol.io/) — Official protocol spec
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) — Low-level SDK
- [Dedalus MCP Documentation](docs/dedalus_mcp/) — Framework guides
