## User Interaction Model

Prompts are designed to be **user-controlled**, meaning they are exposed from servers to
clients with the intention of the user being able to explicitly select them for use.

Typically, prompts would be triggered through user-initiated commands in the user
interface, which allows users to naturally discover and invoke available prompts.

For example, as slash commands:

<img src="https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/specification/2025-06-18/server/slash-command.png?fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=7f003e36d881dd6f3e5b8cbdd85e5ca5" alt="Example of prompt exposed as slash command" data-og-width="293" width="293" data-og-height="106" height="106" data-path="specification/2025-06-18/server/slash-command.png" data-optimize="true" data-opv="3" srcset="https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/specification/2025-06-18/server/slash-command.png?w=280&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=603a7ec1db6f7630749e0b6d0558ea43 280w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/specification/2025-06-18/server/slash-command.png?w=560&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=b9e7dae545ed3b1ffbe8dde360883993 560w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/specification/2025-06-18/server/slash-command.png?w=840&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=8c25c68eebccb025ffe8aed6d58f19f2 840w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/specification/2025-06-18/server/slash-command.png?w=1100&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=a19b889ed688569f49a68311d5e88dfa 1100w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/specification/2025-06-18/server/slash-command.png?w=1650&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=571df0a228861e612304c2ebe829b06c 1650w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/specification/2025-06-18/server/slash-command.png?w=2500&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=8d315246806794b5496c4aaa2cf28e51 2500w" />

However, implementors are free to expose prompts through any interface pattern that suits
their needs—the protocol itself does not mandate any specific user interaction
model.

