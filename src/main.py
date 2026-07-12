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


@st.cache_resource
def get_global_agent_worker():
    # 1. 建立并启动后台 Event Loop & MCP 连接 & AgentCore 组装
    worker = AgentHarness()
    worker.bootstrap()

    return worker


# --- 真正的入口点 ---
# 无论 Streamlit 页面刷新多少次，这段代码只会触发一次初始化，FastAPI 也只启动一次。
agent_worker = get_global_agent_worker()

# 下面继续写你原先的 Streamlit UI 渲染逻辑即可：
run_ui(agent_worker)
