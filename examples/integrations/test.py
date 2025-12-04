import asyncio
from dedalus_labs import AsyncDedalus, DedalusRunner
from dotenv import load_dotenv
from dedalus_labs.utils.stream import stream_async

load_dotenv()

async def main():
    client = AsyncDedalus(base_url="http://localhost:8080")
    runner = DedalusRunner(client)

    result = await runner.run(
        input="Who won Wimbledon 2025?",
        model="google/gemini-3-pro-preview",
        mcp_servers=["tsion/brave-search-mcp"],
        stream=False
    )

    print(result.final_output)

if __name__ == "__main__":
    asyncio.run(main())