import asyncio
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():

    params = StdioServerParameters(
        command=sys.executable,
        args=["hello_mcp.py"],
    )

    async with stdio_client(params) as (read, write):

        print("CONNECTED")

        async with ClientSession(read, write) as session:

            await session.initialize()

            print("INITIALIZED")

            tools = await session.list_tools()

            print(tools)


if __name__ == "__main__":
    asyncio.run(main())