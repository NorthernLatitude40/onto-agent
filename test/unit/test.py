from dotenv import load_dotenv
from typing import Annotated
from typing_extensions import TypedDict

import httpx
from bs4 import BeautifulSoup
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

# 1. 載入金鑰
load_dotenv()

# ================= 技能一：查天氣 =================
@tool
def get_weather(city: str) -> str:
    """獲取指定城市的即時天氣資訊。"""
    city_lower = city.lower()
    if "東京" in city_lower or "tokyo" in city_lower:
        return "東京目前天氣：晴朗，氣溫 18 度。"
    return f"暫時找不到 {city} 的天氣資訊。"

# ================= 🌟 新增技能二：讀取網頁 =================
@tool
def fetch_web_page(url: str) -> str:
    """給定一個網頁網址 (URL)，抓取並解析該網頁的純文字內容。

    Args:
        url: 完整的網頁網址，例如 'https://example.com'
    """
    try:
        # 使用 httpx 去下載網頁
        headers = {"User-Agent": "Mozilla/5.0"}
        response = httpx.get(url, headers=headers, timeout=10)
        
        # 使用 BeautifulSoup 解析 HTML 並拔掉亂七八糟的標籤，只留純文字
        soup = BeautifulSoup(response.text, "html.parser")
        
        # 移除 script 和 style 標籤
        for script in soup(["script", "style"]):
            script.decompose()
            
        text = soup.get_text(separator="\n")
        # 稍微修剪一下空白，拿前 1000 個字就好，免得太長爆 token
        cleaned_text = "\n".join([line.strip() for line in text.splitlines() if line.strip()])
        return cleaned_text[:1000]
        
    except Exception as e:
        return f"讀取網頁失敗，原因: {str(e)}"


# 3. 把這兩項技能都寫進 Agent 的技能書裡！
tools = [get_weather, fetch_web_page]
tool_node = ToolNode(tools)

# 4. LangGraph 基礎設定
class State(TypedDict):
    messages: Annotated[list, add_messages]

model = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
model_with_tools = model.bind_tools(tools)

def call_model(state: State):
    return {"messages": [model_with_tools.invoke(state["messages"])]}

# 5. 組裝流程圖
workflow = StateGraph(State)
workflow.add_node("agent", call_model)
workflow.add_node("tools", tool_node)

workflow.add_edge(START, "agent")
workflow.add_conditional_edges("agent", tools_condition)
workflow.add_edge("tools", "agent")

app = workflow.compile()

# ================= 🚀 測試網頁爬蟲技能 =================
# 我們給它一個真實的網址，看它會不會主動去爬
inputs = {"messages": [("user", "幫我看一下這個網頁的內容在寫什麼：https://cg.originmood.com/NewsContent/zh_TW/mlbb_news_17394.html")]}

print("--- LangGraph 雙技能測試開始 ---")
for output in app.stream(inputs, stream_mode="values"):
    last_message = output["messages"][-1]
    print(f"\n[{last_message.type.upper()}]:")
    if last_message.content:
        print(last_message.content)
    else:
        print(f"(呼叫工具: {last_message.tool_calls[0]['name']}, 參數: {last_message.tool_calls[0]['args']})")