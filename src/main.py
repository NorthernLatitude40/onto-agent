import os
import sys

# 获取当前 main.py 的上一级目录（即 src 的上级：根目录）
root_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_path not in sys.path:
    sys.path.insert(0, root_path)

import threading  # 🌟 补上这行，解决 NameError
import uvicorn
import streamlit as st

from core.harness import AgentHarness
from api.agent_api import create_api
from ui.app import run_ui


def run_bg_api(api_app):
    print("🚀 [FastAPI] 大腦對外 API 服務正在啟動，監聽 http://127.0.0.1:8000 ...")
    uvicorn.run(api_app, host="0.0.0.0", port=8000, log_level="warning")


@st.cache_resource
def get_global_agent_worker():
    # 1. 建立并启动后台 Event Loop & MCP 连接 & AgentCore 组装
    worker = AgentHarness()
    worker.bootstrap()

    # 2. 核心就绪后，创建 API 实例并绑定该 worker
    api_app = create_api(worker)

    # 3. 启动开在 8000 端口的 FastAPI 线程
    print("🌟 正在啟動背景 8000 埠口 API 服務...")
    bg_thread = threading.Thread(target=run_bg_api, args=(api_app,), daemon=True)
    bg_thread.start()

    return worker


# --- 真正的入口点 ---
# 无论 Streamlit 页面刷新多少次，这段代码只会触发一次初始化，FastAPI 也只启动一次。
agent_worker = get_global_agent_worker()

# 下面继续写你原先的 Streamlit UI 渲染逻辑即可：
run_ui(agent_worker)
# ... 省略原先的 chat 界面逻辑 ...
# 调用时直接使用：agent_worker.sync_invoke(...)
