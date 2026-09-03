import json
import os
import time
import asyncio
import redis
from dotenv import load_dotenv

# 1. 加载 .env 环境变量
load_dotenv()

from src.core.llm_router import router as base_llm
from src.core.voyager_agent.skill_library import SkillLibrary
from core.voyager_agent.voyager_strategy import CustomSandboxVoyagerStrategy
from src.common.redis_client import redis_client


def run_worker():
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    gemini_api_key = os.getenv("GEMINI_API_KEY")

    if not all([supabase_url, supabase_key, gemini_api_key]):
        raise ValueError(
            "❌ 缺少必要的环境变量！请检查 .env 中是否配置了 SUPABASE_URL, SUPABASE_KEY, GEMINI_API_KEY"
        )

    skill_library = SkillLibrary(
        supabase_url=supabase_url,
        supabase_key=supabase_key,
        gemini_api_key=gemini_api_key,
    )

    print("🤖 [Voyager Worker] 已启动，监听 Redis 队列 (voyager:task_queue)...")

    while True:
        try:
            # 2. 将 timeout 设为 20 秒轮询心跳，防止 Upstash/云端 Socket 读超时
            pop_result = redis_client.brpop("voyager:task_queue", timeout=20)
            
            # 超时无任务时返回 None，安全跳过
            if not pop_result:
                continue

            _, raw_payload = pop_result
            data = json.loads(raw_payload)

            task_id = data["task_id"]
            task_description = data["task_description"]

            print(f"\n⚙️ [Voyager Worker] 收到任务: {task_id}")
            print(f"📝 任务描述: {task_description}")

            # 更新状态为 RUNNING
            redis_client.hset(f"voyager:status:{task_id}", "status", "RUNNING")

            # 实例化策略图并异步执行
            voyager = CustomSandboxVoyagerStrategy(skill_library, base_llm)
            voyager_graph = voyager.build_graph()

            result = asyncio.run(
                voyager_graph.ainvoke({"task": task_description})
            )

            # 更新 Redis 状态
            if result.get("success"):
                redis_client.hset(
                    f"voyager:status:{task_id}",
                    mapping={
                        "status": "SUCCESS",
                        "generated_code": result.get("generated_code", ""),
                        "execution_result": str(
                            result.get("execution_result", "")
                        ),
                    },
                )
                print(f"✅ [Voyager Worker] 任务 {task_id} 成功完成并已归档技能！")
            else:
                redis_client.hset(
                    f"voyager:status:{task_id}",
                    mapping={
                        "status": "FAILED",
                        "error_log": str(result.get("error_log", "")),
                        "retry_count": str(result.get("retry_count", 0)),
                    },
                )
                print(f"❌ [Voyager Worker] 任务 {task_id} 沙盒自愈失败。")

        except (redis.exceptions.TimeoutError, redis.exceptions.ConnectionError):
            # 捕获网络抖动与 Socket 超时，静默忽略并重试
            continue
        except Exception as e:
            print(f"⚠️ [Voyager Worker] 处理任务时发生未知异常: {e}")
            time.sleep(1)


if __name__ == "__main__":
    run_worker()