import asyncio

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

server_params = StdioServerParameters(
    command="python",
    args=["db_mcp_server.py"]
)

async def main():
    async with stdio_client(server_params) as (read, write):

        async with ClientSession(read, write) as session:

            await session.initialize()

            print("INIT OK")

            tools = await session.list_tools()

            print(tools)

asyncio.run(main())