from mcp.client.streamable_http import streamablehttp_client


def main() -> None:
    client = streamablehttp_client(url="http://127.0.0.1:3000/mcp")
    tools = client.list_tools()
    print("tools/list:", tools)

    response = client.call_tool("add", {"a": 10, "b": 7})
    print("add result:", response)


if __name__ == "__main__":
    main()
