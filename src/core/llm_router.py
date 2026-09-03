import copy
import time
from typing import Any, List

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from src.config.config import settings


class LLMRouter:
    """
    統一管理所有 LLM 輪換與 Failover 機制。

    Gemini -> Groq -> Siliconflow -> OpenRouter -> HuggingFace
    """

    def __init__(self):
        self.gemini_available = True
        self.groq_available = True
        self.siliconflow_available = True
        self.openrouter_available = True

        # ----------------------------
        # Gemini (主力)
        # ----------------------------
        self.gemini = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            api_key=settings.GEMINI_API_KEY,
            temperature=0,
            max_retries=2,
        )

        # ----------------------------
        # Groq (修正模型名稱為官方標準：qwen-2.5-32b / llama-3.3-70b-versatile)
        # ----------------------------
        self.groq = ChatGroq(
            model="qwen/qwen3.8-27b",
            groq_api_key=settings.GROQ_API_KEY,
            temperature=0,
        )

        # ----------------------------
        # Siliconflow
        # ----------------------------
        self.siliconflow = ChatOpenAI(
            model="Qwen/Qwen2.5-7B-Instruct",
            openai_api_key=settings.SILICONFLOW_API_KEY,
            base_url="https://api.siliconflow.cn/v1",
            temperature=0,
        )

        # ----------------------------
        # OpenRouter (替換為穩定可用的免費模型 ID)
        # ----------------------------
        self.openrouter = ChatOpenAI(
            model="deepseek/deepseek-r1:free",
            openai_api_key=settings.OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
            temperature=0,
        )

        # ----------------------------
        # HuggingFace (備用)
        # ----------------------------
        hf_endpoint = HuggingFaceEndpoint(
            repo_id="meta-llama/Llama-3.1-8B-Instruct",
            huggingfacehub_api_token=settings.HUGGINGFACEHUB_API_TOKEN,
            temperature=0.1,
            task="text-generation",
        )

        self.huggingface = ChatHuggingFace(
            llm=hf_endpoint,
        )

    # ===========================================================
    # 消息安全清洗 (防止 Groq / Gemini 因格式拒絕請求)
    # ===========================================================

    def _sanitize_messages(self, messages: Any) -> List[BaseMessage]:
        """
        修正 Groq 及 Gemini 的 Chat Template 限制：
        1. 確保 content 不為空
        2. 確保消息列表中至少包含一條 HumanMessage (user)
        """
        if not isinstance(messages, list):
            return messages

        cleaned_messages = []
        has_human_msg = False

        for msg in messages:
            if isinstance(msg, BaseMessage):
                # 防止空內容導致 Gemini 報錯 "contents are required"
                if not msg.content or (isinstance(msg.content, str) and not msg.content.strip()):
                    continue
                if isinstance(msg, HumanMessage):
                    has_human_msg = True
                cleaned_messages.append(msg)

        # 粗暴兜底：如果完全沒有消息，添加預設 HumanMessage
        if not cleaned_messages:
            cleaned_messages.append(HumanMessage(content="Hello"))
            has_human_msg = True

        # 如果只有 SystemMessage，Groq 會報錯 "No user query found in messages"
        if not has_human_msg:
            cleaned_messages.append(HumanMessage(content="Please process the instruction above."))

        return cleaned_messages

    def get_model(self):
        """獲取當前優先可用的底層 ChatModel 實例"""
        if self.gemini_available and getattr(settings, "GEMINI_API_KEY", None):
            return self.gemini
        if self.groq_available and getattr(settings, "GROQ_API_KEY", None):
            return self.groq
        if self.siliconflow_available and getattr(settings, "SILICONFLOW_API_KEY", None):
            return self.siliconflow
        if self.openrouter_available and getattr(settings, "OPENROUTER_API_KEY", None):
            return self.openrouter
        return self.huggingface

    def get_num_tokens_from_messages(self, messages: list[BaseMessage]) -> int:
        """字符數估算 Token 兜底算法，防範非 OpenAI 模型 API 崩潰"""
        total_text = "".join([str(m.content) for m in messages if m and m.content])
        return max(1, len(total_text) // 2)

    def with_structured_output(self, schema: type[BaseModel]):
        """為支援的模型開啟 Structured Output"""
        for provider in ["gemini", "groq", "siliconflow", "openrouter"]:
            model_inst = getattr(self, provider, None)
            if model_inst and hasattr(model_inst, "with_structured_output"):
                try:
                    setattr(self, provider, model_inst.with_structured_output(schema))
                except Exception as e:
                    print(f"⚠️ {provider.capitalize()} 不支援 structured_output: {e}")
        return self

    # ===========================================================
    # Tool Binding
    # ===========================================================

    def bind_tools(self, tools, **kwargs):
        """為各模型綁定 Tool，使用深拷貝防止多 Agent 交叉污染"""
        new_router = copy.copy(self)

        if self.gemini_available and hasattr(self.gemini, "bind_tools"):
            try:
                new_router.gemini = self.gemini.bind_tools(tools)
            except Exception:
                pass

        if self.groq_available and hasattr(self.groq, "bind_tools"):
            try:
                new_router.groq = self.groq.bind_tools(tools)
            except Exception:
                pass

        if self.siliconflow_available and hasattr(self.siliconflow, "bind_tools"):
            try:
                new_router.siliconflow = self.siliconflow.bind_tools(tools)
            except Exception:
                pass

        if self.openrouter_available and hasattr(self.openrouter, "bind_tools"):
            try:
                new_router.openrouter = self.openrouter.bind_tools(tools)
            except Exception:
                pass

        return new_router

    # ===========================================================
    # 同步 & 异步 调用 (Invoke & Ainvoke)
    # ===========================================================

    def invoke(self, messages: Any, config=None, **kwargs):
        safe_messages = self._sanitize_messages(messages)

        # 1. Gemini
        if self.gemini_available and getattr(settings, "GEMINI_API_KEY", None):
            try:
                print("🔄 [Level 1] Gemini")
                response = self.gemini.invoke(safe_messages, config=config, **kwargs)
                print("✅ Gemini Success")
                return response
            except Exception as e:
                print(f"❌ Gemini Failed: {e}")
                self.gemini_available = False
                time.sleep(0.5)

        # 2. Groq
        if self.groq_available and getattr(settings, "GROQ_API_KEY", None):
            try:
                print("⚡ [Level 2] Groq")
                response = self.groq.invoke(safe_messages, config=config, **kwargs)
                print("✅ Groq Success")
                return response
            except Exception as e:
                print(f"❌ Groq Failed: {e}")
                self.groq_available = False
                time.sleep(0.5)

        # 3. Siliconflow
        # if self.siliconflow_available and getattr(settings, "SILICONFLOW_API_KEY", None):
        #     try:
        #         print("🌊 [Level 3] Siliconflow")
        #         response = self.siliconflow.invoke(messages, config=config)
        #         print("✅ Siliconflow Success")
        #         return response
        #     except Exception as e:
        #         print(f"❌ Siliconflow Failed: {e}")
        #         self.siliconflow_available = False
        #         time.sleep(0.5)

        # 4. OpenRouter
        if self.openrouter_available and getattr(settings, "OPENROUTER_API_KEY", None):
            try:
                print("🚀 [Level 4] OpenRouter")
                response = self.openrouter.invoke(safe_messages, config=config, **kwargs)
                print("✅ OpenRouter Success")
                return response
            except Exception as e:
                print(f"❌ OpenRouter Failed: {e}")
                self.openrouter_available = False
                time.sleep(0.5)

        # 5. HuggingFace
        if getattr(settings, "HUGGINGFACEHUB_API_TOKEN", None):
            try:
                print("🤗 [Level 5] HuggingFace")
                response = self.huggingface.invoke(safe_messages, config=config, **kwargs)
                print("✅ HuggingFace Success")
                return response
            except Exception as e:
                print(f"❌ HuggingFace Failed: {e}")

        raise RuntimeError("所有模型均不可使用或呼叫失敗，請檢查 API Keys 或帳戶額度。")

    async def ainvoke(self, messages: Any, config=None, **kwargs):
        """LangGraph 异步调用的关键兼容方法"""
        safe_messages = self._sanitize_messages(messages)

        # 1. Gemini
        if self.gemini_available and getattr(settings, "GEMINI_API_KEY", None):
            try:
                print("🔄 [Level 1] Gemini (Async)")
                response = await self.gemini.ainvoke(safe_messages, config=config, **kwargs)
                print("✅ Gemini Success")
                return response
            except Exception as e:
                print(f"❌ Gemini Failed: {e}")
                self.gemini_available = False

        # 2. Groq
        if self.groq_available and getattr(settings, "GROQ_API_KEY", None):
            try:
                print("⚡ [Level 2] Groq (Async)")
                response = await self.groq.ainvoke(safe_messages, config=config, **kwargs)
                print("✅ Groq Success")
                return response
            except Exception as e:
                print(f"❌ Groq Failed: {e}")
                self.groq_available = False

        # 3. Siliconflow
        if self.siliconflow_available and getattr(settings, "SILICONFLOW_API_KEY", None):
            try:
                print("🌊 [Level 3] Siliconflow (Async)")
                response = await self.siliconflow.ainvoke(safe_messages, config=config, **kwargs)
                print("✅ Siliconflow Success")
                return response
            except Exception as e:
                print(f"❌ Siliconflow Failed: {e}")
                self.siliconflow_available = False

        # 4. OpenRouter
        if self.openrouter_available and getattr(settings, "OPENROUTER_API_KEY", None):
            try:
                print("🚀 [Level 4] OpenRouter (Async)")
                response = await self.openrouter.ainvoke(safe_messages, config=config, **kwargs)
                print("✅ OpenRouter Success")
                return response
            except Exception as e:
                print(f"❌ OpenRouter Failed: {e}")
                self.openrouter_available = False

        # 5. HuggingFace
        if getattr(settings, "HUGGINGFACEHUB_API_TOKEN", None):
            try:
                print("🤗 [Level 5] HuggingFace (Async)")
                response = await self.huggingface.ainvoke(safe_messages, config=config, **kwargs)
                print("✅ HuggingFace Success")
                return response
            except Exception as e:
                print(f"❌ HuggingFace Failed: {e}")

        raise RuntimeError("所有模型均不可使用或呼叫失敗，請檢查 API Keys 或帳戶額度。")

    def reset(self):
        """恢復所有模型可用狀態"""
        self.gemini_available = True
        self.groq_available = True
        self.siliconflow_available = True
        self.openrouter_available = True

    @property
    def status(self):
        return {
            "gemini": self.gemini_available,
            "groq": self.groq_available,
            "siliconflow": self.siliconflow_available,
            "openrouter": self.openrouter_available,
            "huggingface": bool(getattr(settings, "HUGGINGFACEHUB_API_TOKEN", None)),
        }


router = LLMRouter()