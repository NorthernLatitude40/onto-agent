import json
import redis
import asyncio
from src.core.shop_agent.shop_strategy import ShopAgentStrategy

def check_redis_queue():
    """辅助查看 Redis 状态"""
    r = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)
    print("\n--- 🔍 Redis 当前状态 ---")
    print(f"队列任务数: {r.llen('voyager:task_queue')}")
    keys = r.keys("voyager:status:*")
    for key in keys:
        print(f"任务状态 ({key}): {r.hgetall(key)}")
    print("-------------------------\n")

async def test_async_dispatch():
    # 1. 实例化主 Agent
    strategy = ShopAgentStrategy()
    strategy.build(mcp_tools=[])

    # 2. 模拟触发需要 Voyager 新建工具的请求
    user_query = "请帮我写一个专门计算二手手机折旧率的工具，输入原价和使用月数，按每月折旧2%计算。"
    print(f"👤 用户输入: {user_query}")

    # 3. 调用主 Agent (应该会在几秒内快速返回，不卡顿)
    config = {"configurable": {"thread_id": "test_thread_1"}}
    res = await strategy.ainvoke({"messages": [("user", user_query)]}, config=config)
    
    last_msg = res["messages"][-1]
    print(f"\n🤖 主 Agent 快速响应:\n{last_msg.content}")

if __name__ == "__main__":
    check_redis_queue()
    asyncio.run(test_async_dispatch())
    check_redis_queue()