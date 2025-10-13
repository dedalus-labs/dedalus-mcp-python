## User Interaction Model

Resources in MCP are designed to be **application-driven**, with host applications
determining how to incorporate context based on their needs.

For example, applications could:

* Expose resources through UI elements for explicit selection, in a tree or list view
* Allow the user to search through and filter available resources
* Implement automatic context inclusion, based on heuristics or the AI model's selection

<img src="https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/specification/2025-06-18/server/resource-picker.png?fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=133fa885ef6e9c2e20049da5c33f4386" alt="Example of resource context picker" data-og-width="174" width="174" data-og-height="181" height="181" data-path="specification/2025-06-18/server/resource-picker.png" data-optimize="true" data-opv="3" srcset="https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/specification/2025-06-18/server/resource-picker.png?w=280&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=206f6dcc471323787199d7539a16b7d3 280w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/specification/2025-06-18/server/resource-picker.png?w=560&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=576d4587b4fdfe91bb14d8f77eb40e35 560w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/specification/2025-06-18/server/resource-picker.png?w=840&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=c0d19d08d43fe75f27ee43fb89d5e31b 840w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/specification/2025-06-18/server/resource-picker.png?w=1100&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=463f52a7f01214ad65731626bedc4a50 1100w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/specification/2025-06-18/server/resource-picker.png?w=1650&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=7478600400e55427ba7d3649ae7e8c88 1650w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/specification/2025-06-18/server/resource-picker.png?w=2500&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=c7ec8e376a75bf1aa5d5fcc235a74d2b 2500w" />

However, implementations are free to expose resources through any interface pattern that
suits their needs—the protocol itself does not mandate any specific user
interaction model.

