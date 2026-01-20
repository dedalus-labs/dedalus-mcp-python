# Connect to local MCP servers
Source: https://modelcontextprotocol.io/docs/develop/connect-local-servers

Learn how to extend Claude Desktop with local MCP servers to enable file system access and other powerful integrations

Model Context Protocol (MCP) servers extend AI applications' capabilities by providing secure, controlled access to local resources and tools. Many clients support MCP, enabling diverse integration possibilities across different platforms and applications.

This guide demonstrates how to connect to local MCP servers using Claude Desktop as an example, one of the [many clients that support MCP](/clients). While we focus on Claude Desktop's implementation, the concepts apply broadly to other MCP-compatible clients. By the end of this tutorial, Claude will be able to interact with files on your computer, create new documents, organize folders, and search through your file system—all with your explicit permission for each action.

<Frame>
  <img src="https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-filesystem.png?fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=629d7e754dc358d71a408d6ce970c1b1" alt="Claude Desktop with filesystem integration showing file management capabilities" data-og-width="1732" width="1732" data-og-height="2060" height="2060" data-path="images/quickstart-filesystem.png" data-optimize="true" data-opv="3" srcset="https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-filesystem.png?w=280&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=0758ee60aee8acc3035727957612351f 280w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-filesystem.png?w=560&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=3bc6d3ea4a3cd38b6d031ac386700c62 560w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-filesystem.png?w=840&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=9d75e8729b08b452f2e0d08bff8ce393 840w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-filesystem.png?w=1100&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=b35c6b531daa84b4ba4b06c9223b1ee2 1100w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-filesystem.png?w=1650&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=c4bb491d17a65e038120b5c39031ab7f 1650w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-filesystem.png?w=2500&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=ea7a0ad5ae5eeb866222f4020dc7bba3 2500w" />
</Frame>
