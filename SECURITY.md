# Security Policy

## Reporting Vulnerabilities

**Do not open public issues for security vulnerabilities.**

Email security reports to: [security@dedaluslabs.ai](mailto:security@dedaluslabs.ai)

Include:

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

We will acknowledge your report within 48 hours and provide a detailed response within 7 days.

## Supported Versions

| Version | Supported |
|---------|-----------|
| main    | ✅ Active development |
| < 1.0   | ⚠️ Pre-release, best-effort |

## Security Model

OpenMCP is a framework for building MCP servers and clients. Security considerations:

### Server-Side

- **Input validation**: All tool/resource inputs validated via Pydantic
- **Type safety**: Full type hints enforced via mypy
- **Context isolation**: Each request gets isolated context

### Client-Side

- **Transport security**: HTTPS recommended for HTTP transport
- **Token handling**: OAuth tokens managed securely when using authorization

### Known Limitations

This is pre-1.0 software. Areas still being hardened:

1. **Authorization flows**: OAuth support is opt-in and requires proper configuration
2. **Resource access**: No built-in sandboxing of resource handlers
3. **Tool execution**: Tools run in the same process as the server

## Security Best Practices for Users

### Required

- Use TLS for all HTTP transports in production
- Validate all external inputs in your tool/resource handlers
- Don't expose sensitive data in error messages
- Use environment variables for secrets, never hardcode

### Recommended

- Enable authorization for multi-tenant deployments
- Audit log all tool invocations
- Set appropriate timeouts for long-running operations
- Pin dependencies to avoid supply chain attacks

## Disclosure Policy

We follow coordinated disclosure:

1. Reporter submits vulnerability privately
2. We acknowledge within 48 hours
3. We investigate and develop fix
4. We release fix and credit reporter (unless anonymity requested)
5. Public disclosure after 90 days or when fix is deployed

## Bug Bounty

We don't currently have a formal bug bounty program. Significant security contributions will be acknowledged in release notes.

## Contact

- Security issues: [security@dedaluslabs.ai](mailto:security@dedaluslabs.ai)
- General questions: [oss@dedaluslabs.ai](mailto:oss@dedaluslabs.ai)
