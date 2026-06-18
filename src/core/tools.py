import httpx
from langchain_core.tools import tool
from src.config.config import ANYTHINGLLM_BASE_URL, ANYTHINGLLM_API_KEY, WORKSPACE_SLUG


@tool
def search_official_knowledge_base(query: str) -> str:
    """RAG 查询官方售票知识库"""
    url = f"{ANYTHINGLLM_BASE_URL}/workspace/{WORKSPACE_SLUG}/chat"
    payload = {
        "message": query,
        "mode": "query",
        "model": "current",
        "temperature": 0.0
    }
    headers = {
        "Authorization": f"Bearer {ANYTHINGLLM_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        r = httpx.post(url, json=payload, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()

        sources = data.get("sources", [])
        if sources:
            return "\n\n".join(
                src.get("text", "").strip()
                for src in sources if src.get("text")
            )

        return data.get("textResponse", "")

    except Exception as e:
        return f"RAG error: {e}"


@tool
def get_weather(city: str) -> str:
    """获取指定城市的实时天气信息"""
    if "东京" in city or "tokyo" in city.lower():
        return "东京：晴 18°C"
    if "台北" in city or "taipei" in city.lower():
        return "台北：阴 22°C"
    return f"{city} 天气未知"