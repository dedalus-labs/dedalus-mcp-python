# Client Capability Audit

Mapping of Dedalus MCP’s client wrapper (`src/dedalus_mcp/client/app.py`) to the
features called out in `docs/mcp/core/understanding-mcp-clients`.

| Spec focus | Requirement | Dedalus MCP implementation | Notes |
| --- | --- | --- | --- |
| Sampling | Allow servers to request `sampling/createMessage` via the client with human-in-the-loop control. | `ClientCapabilitiesConfig.sampling` and `_build_sampling_handler()` (`src/dedalus_mcp/client/app.py:44-123,156-168`) forward callbacks through `ClientSession`. | Host application supplies handler; we surface params/results unchanged per spec. |
| Elicitation | Enable servers to solicit structured user input mid-flow. | `ClientCapabilitiesConfig.elicitation`, `_build_elicitation_handler()` (`src/dedalus_mcp/client/app.py:44-123,170-178`). | Mirrors reference SDK expectations; host UI controls presentation. |
| Roots | Advertise and update accessible file roots, emitting `roots/list_changed`. | `_supports_roots`, `update_roots`, `list_roots`, `_build_roots_handler` (`src/dedalus_mcp/client/app.py:62-155,180-214`). | Thread-safe updates via `anyio.Lock`; docs guide apps on when to enable roots. |
| Logging | Relay `notifications/logging/message` to client-side observability. | `ClientCapabilitiesConfig.logging`, `_build_logging_handler` (`src/dedalus_mcp/client/app.py:44-123,180-189`). | Handlers receive validated params; optional per host needs. |
| Cancellation | Allow clients to cancel in-flight server requests. | `cancel_request()` (`src/dedalus_mcp/client/app.py:131-143`). | Emits `notifications/cancelled` in-line with `docs/mcp/core/cancellation`. |
| Transport integration | Work with STDIO and Streamable HTTP transports, including helper builders. | `src/dedalus_mcp/client/transports.py` (new module) plus docs in `docs/dedalus_mcp/transports.md`. | Provides `stdio_client`, `streamable_http_client`, and lambda-friendly variants; aligns with transport guidance. |

### Observations

* Advanced UX patterns (e.g., prompt/resource argument suggestion) remain client responsibilities; Dedalus MCP exposes raw data but does not implement UI heuristics.
* Capability handlers return the raw types from the MCP specification, keeping the wrapper thin and predictable.

