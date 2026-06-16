import asyncio
import traceback
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

server_params = StdioServerParameters(
    command="python",
    args=["db_mcp_server.py"]
)

async def main():
    try:
        async with stdio_client(server_params) as (read, write):
            # 建立 session
            async with ClientSession(read, write) as session:

                print("INITIALIZING")
                # 初始化 session
                await asyncio.wait_for(
                    session.initialize(),
                    timeout=10
                )

                print("STDIO OK")
                #關閉 session
    except Exception:
        traceback.print_exc()

asyncio.run(main())