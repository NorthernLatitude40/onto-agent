import pytest

pytestmark = pytest.mark.integration
import sys

import pytest
from mcp import ClientSession
from mcp.client.sse import sse_client

print("PYTHON =", sys.executable)

@pytest.mark.integration
@pytest.mark.asyncio
async def test_mcp_sse_connection():
    """測試 MCP SSE 連線與初始化"""
    
    # 使用 sse_client 進行連線
    async with sse_client("http://127.0.0.1:8000/sse") as (read, write):
        print("SSE OK")

        # 透過 async context manager 正確管理 session 生命週期
        async with ClientSession(read, write) as session:
            print("Initializing...")

            # 執行初始化並加上 10 秒 Timeout
            await session.initialize()

            print("INIT OK")