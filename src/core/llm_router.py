import time
import copy
from typing import Any

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from src.config.config import settings


class LLMRouter:
    """
    統一管理所有 LLM。

    Gemini
        ↓
    OpenRouter
        ↓
    HuggingFace
    """

    def __init__(self):
        self.gemini_available = True
        self.openrouter_available = True

        # ----------------------------
        # Gemini
        # ----------------------------
        self.gemini = ChatGoogleGenerativeAI(
            model="gemini-3.5-flash",
            api_key=settings.GEMINI_API_KEY,
            temperature=0,
        )

        # ----------------------------
        # OpenRouter
        # ----------------------------
        self.openrouter = ChatOpenAI(
            model="google/gemma-4-31b-it:free",
            openai_api_key=settings.OPENROUTER_API_KEY,
            openai_api_base="https://openrouter.ai/api/v1",
            temperature=0,
        )

        # ----------------------------
        # HuggingFace
        # ----------------------------
        hf_endpoint = HuggingFaceEndpoint(
            repo_id="Qwen/Qwen2.5-7B-Instruct",
            huggingfacehub_api_token=settings.HUGGINGFACEHUB_API_TOKEN,
            temperature=0.1,
            task="text-generation",
        )

        self.huggingface = ChatHuggingFace(
            llm=hf_endpoint,
        )

    def with_structured_output(
            self,
            schema: type[BaseModel],
        ):
            """
            為支援的模型開啟 Structured Output，不支援的則略過或印出警告
            """
            try:
                self.gemini = self.gemini.with_structured_output(schema)
            except (ImportError, Exception) as e:
                print(f"⚠️ Gemini 不支援 structured_output: {e}")

            try:
                self.openrouter = self.openrouter.with_structured_output(schema)
            except (ImportError, Exception) as e:
                print(f"⚠️ OpenRouter 不支援 structured_output: {e}")

            # 💡 HuggingFace 不支援 Pydantic schema 呼叫，因此這裡安全略過，
            # 避免程式崩潰。若有需要可改用 Prompt 手動解析。
            print("ℹ️ HuggingFace (Qwen) 不支援原生 Structured Output，已略過此設定。")

            return self

    # ===========================================================
    # Tool Calling
    # ===========================================================

    def bind_tools(self, tools):
        """
        创建一个独立的 Router 副本并绑定工具，解决多 Agent 工具冲突/覆盖问题
        """
        # 1. 复制一份全新的 Router 容器
        new_router = copy.copy(self)

        new_router.gemini = self.gemini.bind_tools(
            tools,
            strict=False,
        )

        new_router.openrouter = self.openrouter.bind_tools(
            tools,
        )

        new_router.huggingface = self.huggingface.bind_tools(
            tools,
        )

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
        自動模型路由

        Gemini
            ↓
        OpenRouter
            ↓
        HuggingFace
        """

        # ===================================================
        # Level 1
        # ===================================================

        if self.gemini_available:
            try:

                print("🔄 [Level 1] Gemini")

                response = self.gemini.invoke(
                    messages,
                    config=config,
                )

                print("✅ Gemini Success")

                return response

            except (ImportError, Exception) as e:

                print(f"❌ Gemini Failed: {e}")

                self.gemini_available = False

                time.sleep(1)

        # ===================================================
        # Level 2
        # ===================================================

        if self.openrouter_available and settings.OPENROUTER_API_KEY:

            try:

                print("🚀 [Level 2] OpenRouter")

                response = self.openrouter.invoke(
                    messages,
                    config=config,
                )

                print("✅ OpenRouter Success")

                return response

            except (ImportError, Exception) as e:

                print(f"❌ OpenRouter Failed: {e}")

                self.openrouter_available = False

                time.sleep(1)

        # ===================================================
        # Level 3
        # ===================================================

        if settings.HUGGINGFACEHUB_API_TOKEN:

            print("⚡ [Level 3] HuggingFace")

            return self.huggingface.invoke(
                messages,
                config=config,
            )

        raise RuntimeError(
            "所有模型均不可使用，且未配置 HuggingFace Token。"
        )

    # ===========================================================
    # Reset
    # ===========================================================

    def reset(self):
        """
        恢復所有模型可用狀態
        """

        self.gemini_available = True
        self.openrouter_available = True

    # ===========================================================
    # Health
    # ===========================================================

    @property
    def status(self):

        return {
            "gemini": self.gemini_available,
            "openrouter": self.openrouter_available,
            "huggingface": bool(settings.HUGGINGFACEHUB_API_TOKEN),
        }
    
router = LLMRouter()