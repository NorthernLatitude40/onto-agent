import os
import modal
from pathlib import Path

# 1. 动态获取项目根目录与 src 目录路径
# 当前文件位于 src/core/voyager_agent/modal_worker.py，向上 3 层定位到 src 目录
# 定位项目根目录 (含有 pyproject.toml / uv.lock 的目录)
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent.parent.parent  # 向上4层到项目根目录
src_dir = project_root / "src"

# 2. 定义 Modal App
app = modal.App("voyager-worker")

# 使用 Modal 的 pip_install_from_pyproject 或 pip_install_from_requirements
image = (
    modal.Image.debian_slim()
    # 方式 A：如果使用的是 uv 管理的 pyproject.toml，直接解析依赖
    .pip_install_from_pyproject(project_root / "pyproject.toml")
    
    # 挂载本地 src 源码至 Modal 容器
    .add_local_dir(local_path=src_dir, remote_path="/root/src")
)


@app.function(
    image=image,
    # 建议在 Modal Dashboard (https://modal.com/secrets) 创建名为 my-custom-secrets 的 Secret
    secrets=[modal.Secret.from_name("my-custom-secrets")],
    timeout=600  # 针对 Agent 沙盒多轮自愈/迭代，超时上限设为 10 分钟
)
def run_voyager_task(task_id: str, task_description: str):
    """
    Serverless 触发函数：收到任务后自动拉起容器，运行 Agent 逻辑，更新 Redis 状态
    """
    # 延迟导入，防止镜像构建/解析阶段因 Python path 找不到本地模块
    import sys
    if "/root" not in sys.path:
        sys.path.append("/root")

    from src.core.llm_router import router as base_llm
    from src.core.voyager_agent.skill_library import SkillLibrary
    from src.core.voyager_agent.voyager_strategy import CustomSandboxVoyagerStrategy
    from src.common.redis_client import redis_client

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    gemini_api_key = os.getenv("GEMINI_API_KEY")

    if not all([supabase_url, supabase_key, gemini_api_key]):
        raise ValueError("❌ 缺少必要的环境变量！请检查 Modal Secrets 控制台中是否配置了 SUPABASE_URL, SUPABASE_KEY, GEMINI_API_KEY")

    print(f"⚙️ [Modal Worker] 开始处理任务: {task_id}")
    print(f"📝 任务描述: {task_description}")

    # 更新 Redis 状态为 RUNNING
    redis_client.hset(f"voyager:status:{task_id}", "status", "RUNNING")

    try:
        skill_library = SkillLibrary(
            supabase_url=supabase_url,
            supabase_key=supabase_key,
            gemini_api_key=gemini_api_key,
        )

        voyager = CustomSandboxVoyagerStrategy(skill_library, base_llm)
        voyager_graph = voyager.build_graph()

        import asyncio
        result = asyncio.run(
            voyager_graph.ainvoke({"task": task_description})
        )

        # 任务成功与失败的状态归档
        if result.get("success"):
            redis_client.hset(
                f"voyager:status:{task_id}",
                mapping={
                    "status": "SUCCESS",
                    "generated_code": result.get("generated_code", ""),
                    "execution_result": str(result.get("execution_result", "")),
                },
            )
            print(f"✅ [Modal Worker] 任务 {task_id} 成功完成！")
            return {"status": "SUCCESS", "task_id": task_id}
        else:
            redis_client.hset(
                f"voyager:status:{task_id}",
                mapping={
                    "status": "FAILED",
                    "error_log": str(result.get("error_log", "")),
                    "retry_count": str(result.get("retry_count", 0)),
                },
            )
            print(f"❌ [Modal Worker] 任务 {task_id} 沙盒自愈失败。")
            return {"status": "FAILED", "task_id": task_id}

    except Exception as e:
        print(f"⚠️ [Modal Worker] 处理任务时发生未知异常: {e}")
        redis_client.hset(
            f"voyager:status:{task_id}",
            mapping={"status": "FAILED", "error_log": str(e)},
        )
        raise e