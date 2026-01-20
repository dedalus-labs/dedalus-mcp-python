## Installing the Filesystem Server

The process involves configuring Claude Desktop to automatically start the Filesystem Server whenever you launch the application. This configuration is done through a JSON file that tells Claude Desktop which servers to run and how to connect to them.

<Steps>
  <Step title="Open Claude Desktop Settings">
    Start by accessing the Claude Desktop settings. Click on the Claude menu in your system's menu bar (not the settings within the Claude window itself) and select "Settings..."

    On macOS, this appears in the top menu bar:

    <Frame style={{ textAlign: "center" }}>
      <img src="https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-menu.png?fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=0c8b57e0e17af3624b6762a3ea944c8e" width="400" alt="Claude Desktop menu showing Settings option" data-og-width="644" data-og-height="568" data-path="images/quickstart-menu.png" data-optimize="true" data-opv="3" srcset="https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-menu.png?w=280&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=f997b6f31398840d3a824fa0eb9fec43 280w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-menu.png?w=560&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=062b0b3c342e4e02a8f2d690a48bcb24 560w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-menu.png?w=840&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=ae9b08052b7ea30b31d27432d8edf19e 840w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-menu.png?w=1100&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=7962cc4fb841fa0a04a3c6de03cf4d3d 1100w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-menu.png?w=1650&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=86bd79431e35b133d0ae4f74265f3d60 1650w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-menu.png?w=2500&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=1b300ae527efb4744aa08d5df94299a0 2500w" />
    </Frame>

    This opens the Claude Desktop configuration window, which is separate from your Claude account settings.
  </Step>

  <Step title="Access Developer Settings">
    In the Settings window, navigate to the "Developer" tab in the left sidebar. This section contains options for configuring MCP servers and other developer features.

    Click the "Edit Config" button to open the configuration file:

    <Frame>
      <img src="https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-developer.png?fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=0fb595490a2f9e15c0301e771a57446c" alt="Developer settings showing Edit Config button" data-og-width="1688" width="1688" data-og-height="534" height="534" data-path="images/quickstart-developer.png" data-optimize="true" data-opv="3" srcset="https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-developer.png?w=280&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=0a7e615ee50a27a4e514668f7cbd9f57 280w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-developer.png?w=560&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=16d6d4721219afd7e2bfa41f0795e7e0 560w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-developer.png?w=840&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=612b1de5516ed7321d5b6939b5b3c823 840w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-developer.png?w=1100&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=840a428450dc0ec97538eb4e05050bcd 1100w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-developer.png?w=1650&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=59ae3a95918ff7f7b15e777c2d606496 1650w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-developer.png?w=2500&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=7838d7f023a281053786870336914f03 2500w" />
    </Frame>

    This action creates a new configuration file if one doesn't exist, or opens your existing configuration. The file is located at:

    * **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
    * **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
  </Step>

  <Step title="Configure the Filesystem Server">
    Replace the contents of the configuration file with the following JSON structure. This configuration tells Claude Desktop to start the Filesystem Server with access to specific directories:

    <CodeGroup>
      ```json macOS
      {
        "mcpServers": {
          "filesystem": {
            "command": "npx",
            "args": [
              "-y",
              "@modelcontextprotocol/server-filesystem",
              "/Users/username/Desktop",
              "/Users/username/Downloads"
            ]
          }
        }
      }
      ```

      ```json Windows
      {
        "mcpServers": {
          "filesystem": {
            "command": "npx",
            "args": [
              "-y",
              "@modelcontextprotocol/server-filesystem",
              "C:\\Users\\username\\Desktop",
              "C:\\Users\\username\\Downloads"
            ]
          }
        }
      }
      ```
    </CodeGroup>

    Replace `username` with your actual computer username. The paths listed in the `args` array specify which directories the Filesystem Server can access. You can modify these paths or add additional directories as needed.

    <Tip>
      **Understanding the Configuration**

      * `"filesystem"`: A friendly name for the server that appears in Claude Desktop
      * `"command": "npx"`: Uses Node.js's npx tool to run the server
      * `"-y"`: Automatically confirms the installation of the server package
      * `"@modelcontextprotocol/server-filesystem"`: The package name of the Filesystem Server
      * The remaining arguments: Directories the server is allowed to access
    </Tip>

    <Warning>
      **Security Consideration**

      Only grant access to directories you're comfortable with Claude reading and modifying. The server runs with your user account permissions, so it can perform any file operations you can perform manually.
    </Warning>
  </Step>

  <Step title="Restart Claude Desktop">
    After saving the configuration file, completely quit Claude Desktop and restart it. The application needs to restart to load the new configuration and start the MCP server.

    Upon successful restart, you'll see an MCP server indicator <img src="https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/claude-desktop-mcp-slider.svg?fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=2742ec3fb97067e8591e68546c90221e" style={{display: 'inline', margin: 0, height: '1.3em'}} data-og-width="24" width="24" data-og-height="24" height="24" data-path="images/claude-desktop-mcp-slider.svg" data-optimize="true" data-opv="3" srcset="https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/claude-desktop-mcp-slider.svg?w=280&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=52839f8519f476623c4fb5bb87ee24bd 280w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/claude-desktop-mcp-slider.svg?w=560&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=f0491976e108286441fc6554309c5c4f 560w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/claude-desktop-mcp-slider.svg?w=840&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=08e83eb102eda755a7db1eb27d16ebff 840w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/claude-desktop-mcp-slider.svg?w=1100&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=2524a80752928b0206e68e8e1890d1aa 1100w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/claude-desktop-mcp-slider.svg?w=1650&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=3c0dc88dadad5ed8e8af316965d00e0b 1650w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/claude-desktop-mcp-slider.svg?w=2500&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=702363a955a631c40c342f9557d5cfdd 2500w" /> in the bottom-right corner of the conversation input box:

    <Frame>
      <img src="https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-slider.png?fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=f80a38b720fc0519079bae26e2aae312" alt="Claude Desktop interface showing MCP server indicator" data-og-width="1414" width="1414" data-og-height="410" height="410" data-path="images/quickstart-slider.png" data-optimize="true" data-opv="3" srcset="https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-slider.png?w=280&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=24a0dc6f30664e953cc185ed0c7abc64 280w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-slider.png?w=560&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=d670a5fd82405775d7bc1e5f20a9a847 560w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-slider.png?w=840&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=5f66fa4bcaaf50ca905415f15af2e276 840w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-slider.png?w=1100&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=4aecd3c4b45c3aaac75a118d2d6edda5 1100w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-slider.png?w=1650&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=c7d321e2d25aa34552057a8866782549 1650w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-slider.png?w=2500&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=25dc1761b40b11ccb727b36183efa57f 2500w" />
    </Frame>

    Click on this indicator to view the available tools provided by the Filesystem Server:

    <Frame style={{ textAlign: "center" }}>
      <img src="https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-tools.png?fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=18f045f27f31f40896d3710ce9a4a0a0" width="400" alt="Available filesystem tools in Claude Desktop" data-og-width="978" data-og-height="902" data-path="images/quickstart-tools.png" data-optimize="true" data-opv="3" srcset="https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-tools.png?w=280&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=298fc5cf79822ee781d15cf6374d8542 280w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-tools.png?w=560&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=c1e39ca66d9191dbe493cdcb52ad3fcb 560w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-tools.png?w=840&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=d797f46eb55126de14328ede4b735967 840w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-tools.png?w=1100&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=fcb9d89b6cef95bf9a3ffcd9231a4026 1100w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-tools.png?w=1650&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=23097f8f8b52a255246aeb83f85f949d 1650w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-tools.png?w=2500&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=0007b81f22a6a9b9a117981091e0221f 2500w" />
    </Frame>

    If the server indicator doesn't appear, refer to the [Troubleshooting](../build-an-mcp-server/troubleshooting.md#troubleshooting) section for debugging steps.
  </Step>
</Steps>
