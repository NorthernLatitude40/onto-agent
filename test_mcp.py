import sys
print("PYTHON =", sys.executable)
import asyncio
import traceback

from mcp import ClientSession
from mcp.client.sse import sse_client

async def main():
    try:
        async with sse_client(
            "http://127.0.0.1:8000/sse"
        ) as (read, write):

            print("SSE OK")

            session = ClientSession(read, write)

            print("Initializing...")

            await asyncio.wait_for(
                session.initialize(),
                timeout=10
            )

            print("INIT OK")

    except Exception:
        traceback.print_exc()

asyncio.run(main())