import copy
import time
from typing import Any

from langchain_core.messages import BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from langchain_openai import ChatOpenAI
from pydantic import BaseModel
from langchain_groq import ChatGroq

from src.config.config import settings


class LLMRouter:
    """
    統一管理所有 LLM 輪換。

    Gemini
        ↓
    Groq
        ↓
    Siliconflow
        ↓
    OpenRouter
        ↓
    HuggingFace
    """

    def __init__(self):
        self.gemini_available = True
        self.groq_available = True
        self.siliconflow_available = True
        self.openrouter_available = True

        # ----------------------------
        # Gemini (主力高配額)
        # ----------------------------
        self.gemini = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            api_key=settings.GEMINI_API_KEY,
            temperature=0,
            max_retries=2,  # 自動處理短暫的 429 限流與重試
        )

        # ----------------------------
        # Groq (極速備用)
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
        # OpenRouter (嚴格使用 :free 模型)
        # ----------------------------
        self.openrouter = ChatOpenAI(
            model="google/gemma-2-9b-it:free",
            openai_api_key=settings.OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
            temperature=0,
        )

        # ----------------------------
        # HuggingFace (最後備用)
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

    def get_model(self):
        """
        獲取當前優先可用的底層 ChatModel 實例
        """
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
        """
        實現 LangChain 要求的 Token 計算接口
        """
        model = self.get_model()
        if hasattr(model, "get_num_tokens_from_messages"):
            try:
                return model.get_num_tokens_from_messages(messages)
            except Exception:
                pass
        
        # 兜底方案：按字符數估算 Token
        total_text = "".join([str(m.content) for m in messages if m and m.content])
        return len(total_text) // 4

    def with_structured_output(
        self,
        schema: type[BaseModel],
    ):
        """
        為支援的模型開啟 Structured Output，不支援的則略過
        """
        for provider in ["gemini", "groq", "siliconflow", "openrouter"]:
            model_inst = getattr(self, provider, None)
            if model_inst and hasattr(model_inst, "with_structured_output"):
                try:
                    setattr(self, provider, model_inst.with_structured_output(schema))
                except Exception as e:
                    print(f"⚠️ {provider.capitalize()} 不支援 structured_output: {e}")

        print("ℹ️ HuggingFace 不支援原生 Structured Output，已略過此設定。")
        return self

    # ===========================================================
    # Tool Calling
    # ===========================================================

    def bind_tools(self, tools):
        """
        創建獨立 Router 副本並綁定工具，解決多 Agent 工具覆蓋問題
        """
        new_router = copy.copy(self)

        new_router.gemini = self.gemini.bind_tools(tools, strict=False)
        new_router.groq = self.groq.bind_tools(tools)
        new_router.siliconflow = self.siliconflow.bind_tools(tools, strict=False)
        new_router.openrouter = self.openrouter.bind_tools(tools)
        new_router.huggingface = self.huggingface.bind_tools(tools)

        return new_router

    # ===========================================================
    # Invoke
    # ===========================================================

    def invoke(
        self,
        messages: Any,
        config=None,
    ):
        """
        自動模型輪換發送：
        Gemini -> Groq -> Siliconflow -> OpenRouter -> HuggingFace
        """
        # 1. Gemini
        if self.gemini_available and getattr(settings, "GEMINI_API_KEY", None):
            try:
                print("🔄 [Level 1] Gemini")
                response = self.gemini.invoke(messages, config=config)
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
                response = self.groq.invoke(messages, config=config)
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
                response = self.openrouter.invoke(messages, config=config)
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
                response = self.huggingface.invoke(messages, config=config)
                print("✅ HuggingFace Success")
                return response
            except Exception as e:
                print(f"❌ HuggingFace Failed: {e}")

        raise RuntimeError(
            "所有模型均不可使用或呼叫失敗，請檢查 API Keys 或帳戶額度。"
        )

    # ===========================================================
    # Reset
    # ===========================================================

    def reset(self):
        """
        恢復所有模型可用狀態
        """
        self.gemini_available = True
        self.groq_available = True
        self.siliconflow_available = True
        self.openrouter_available = True

    # ===========================================================
    # Health
    # ===========================================================

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