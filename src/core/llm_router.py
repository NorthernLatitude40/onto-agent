import copy
import time
from typing import Any, List, Optional

import requests
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from src.config.config import settings


# ===========================================================
# 1. 自定義 Modal Qwen Chat Model 封裝類別
# ===========================================================
class ChatModalQwen(BaseChatModel):
    endpoint_url: str = Field(...)
    timeout: float = 30.0

    @property
    def _llm_type(self) -> str:
        return "modal-qwen-chat"

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        # 將 LangChain messages 拼接到 Prompt
        prompt = ""
        for m in messages:
            if isinstance(m, SystemMessage):
                prompt += f"System: {m.content}\n"
            elif isinstance(m, HumanMessage):
                prompt += f"User: {m.content}\n"
            elif isinstance(m, AIMessage):
                prompt += f"Assistant: {m.content}\n"
            else:
                prompt += f"{m.content}\n"
        prompt += "Assistant: "

        response = requests.post(
            self.endpoint_url,
            json={"prompt": prompt, "max_tokens": kwargs.get("max_tokens", 1024)},
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()

        text = data.get("response", "")
        message = AIMessage(content=text)
        generation = ChatGeneration(message=message)
        return ChatResult(generations=[generation])


# ===========================================================
# 2. LLMRouter 整合 Modal 兜底
# ===========================================================
class LLMRouter:
    """
    統一管理所有 LLM 輪換與 Failover 機制。

    Gemini -> Groq -> Siliconflow -> OpenRouter -> Modal Qwen -> HuggingFace
    """

    def __init__(self):
        self.gemini_available = True
        self.groq_available = True
        self.siliconflow_available = True
        self.openrouter_available = True
        self.modal_available = True

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
        # Groq
        # ----------------------------
        self.groq = ChatGroq(
            model="qwen-2.5-32b",
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
        # OpenRouter
        # ----------------------------
        self.openrouter = ChatOpenAI(
            model="deepseek/deepseek-r1:free",
            openai_api_key=settings.OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
            temperature=0,
        )

        # ----------------------------
        # Modal 自建 Qwen2.5-7B (兜底備用)
        # ----------------------------
        self.modal_qwen = ChatModalQwen(
            endpoint_url="https://bluedreamww--qwen2-5-7b-awq-service-qwenmodel-api.modal.run"
        )

        # ----------------------------
        # HuggingFace (末端備用)
        # ----------------------------
        hf_endpoint = HuggingFaceEndpoint(
            repo_id="meta-llama/Llama-3.1-8B-Instruct",
            huggingfacehub_api_token=settings.HUGGINGFACEHUB_API_TOKEN,
            temperature=0.1,
            task="text-generation",
        )
        self.huggingface = ChatHuggingFace(llm=hf_endpoint)

    def _sanitize_messages(self, messages: Any) -> List[BaseMessage]:
        if not isinstance(messages, list):
            return messages

        cleaned_messages = []
        has_human_msg = False

        for msg in messages:
            if isinstance(msg, BaseMessage):
                if not msg.content or (isinstance(msg.content, str) and not msg.content.strip()):
                    continue
                if isinstance(msg, HumanMessage):
                    has_human_msg = True
                cleaned_messages.append(msg)

        if not cleaned_messages:
            cleaned_messages.append(HumanMessage(content="Hello"))
            has_human_msg = True

        if not has_human_msg:
            cleaned_messages.append(HumanMessage(content="Please process the instruction above."))

        return cleaned_messages

    def invoke(self, messages: Any, config=None, **kwargs):
        safe_messages = self._sanitize_messages(messages)

        # 1. Gemini
        if self.gemini_available and getattr(settings, "GEMINI_API_KEY", None):
            try:
                print("🔄 [Level 1] Gemini")
                return self.gemini.invoke(safe_messages, config=config, **kwargs)
            except Exception as e:
                print(f"❌ Gemini Failed: {e}")
                self.gemini_available = False
                time.sleep(0.5)

        # 2. Groq
        if self.groq_available and getattr(settings, "GROQ_API_KEY", None):
            try:
                print("⚡ [Level 2] Groq")
                return self.groq.invoke(safe_messages, config=config, **kwargs)
            except Exception as e:
                print(f"❌ Groq Failed: {e}")
                self.groq_available = False
                time.sleep(0.5)

        # 3. Siliconflow
        # if self.siliconflow_available and getattr(settings, "SILICONFLOW_API_KEY", None):
        #     try:
        #         print("🌊 [Level 3] Siliconflow")
        #         return self.siliconflow.invoke(safe_messages, config=config, **kwargs)
        #     except Exception as e:
        #         print(f"❌ Siliconflow Failed: {e}")
        #         self.siliconflow_available = False
        #         time.sleep(0.5)

        # 4. OpenRouter
        if self.openrouter_available and getattr(settings, "OPENROUTER_API_KEY", None):
            try:
                print("🚀 [Level 4] OpenRouter")
                return self.openrouter.invoke(safe_messages, config=config, **kwargs)
            except Exception as e:
                print(f"❌ OpenRouter Failed: {e}")
                self.openrouter_available = False
                time.sleep(0.5)

        # 5. Modal Qwen (新增的專屬 GPU 服務兜底)
        if self.modal_available:
            try:
                print("☁️ [Level 5] Modal Private Qwen2.5")
                return self.modal_qwen.invoke(safe_messages, config=config, **kwargs)
            except Exception as e:
                print(f"❌ Modal Qwen Failed: {e}")
                self.modal_available = False
                time.sleep(0.5)

        # 6. HuggingFace
        if getattr(settings, "HUGGINGFACEHUB_API_TOKEN", None):
            try:
                print("🤗 [Level 6] HuggingFace")
                return self.huggingface.invoke(safe_messages, config=config, **kwargs)
            except Exception as e:
                print(f"❌ HuggingFace Failed: {e}")

        raise RuntimeError("所有模型均不可使用或呼叫失敗，請檢查 API Keys 或帳戶額度。")

    async def ainvoke(self, messages: Any, config=None, **kwargs):
        """異步調用路由，當主流 API 失敗時，會降級使用同步包裝的 Modal/HF 服務"""
        safe_messages = self._sanitize_messages(messages)

        # 1. Gemini
        if self.gemini_available and getattr(settings, "GEMINI_API_KEY", None):
            try:
                print("🔄 [Level 1] Gemini (Async)")
                return await self.gemini.ainvoke(safe_messages, config=config, **kwargs)
            except Exception as e:
                print(f"❌ Gemini Failed: {e}")
                self.gemini_available = False

        # 2. Groq
        if self.groq_available and getattr(settings, "GROQ_API_KEY", None):
            try:
                print("⚡ [Level 2] Groq (Async)")
                return await self.groq.ainvoke(safe_messages, config=config, **kwargs)
            except Exception as e:
                print(f"❌ Groq Failed: {e}")
                self.groq_available = False

        # 3. Siliconflow
        if self.siliconflow_available and getattr(settings, "SILICONFLOW_API_KEY", None):
            try:
                print("🌊 [Level 3] Siliconflow (Async)")
                return await self.siliconflow.ainvoke(safe_messages, config=config, **kwargs)
            except Exception as e:
                print(f"❌ Siliconflow Failed: {e}")
                self.siliconflow_available = False

        # 4. OpenRouter
        if self.openrouter_available and getattr(settings, "OPENROUTER_API_KEY", None):
            try:
                print("🚀 [Level 4] OpenRouter (Async)")
                return await self.openrouter.ainvoke(safe_messages, config=config, **kwargs)
            except Exception as e:
                print(f"❌ OpenRouter Failed: {e}")
                self.openrouter_available = False

        # 5. Modal Qwen (降級回同步 invoke 執行)
        if self.modal_available:
            try:
                print("☁️ [Level 5] Modal Private Qwen2.5 (Async Fallback)")
                return self.modal_qwen.invoke(safe_messages, config=config, **kwargs)
            except Exception as e:
                print(f"❌ Modal Qwen Failed: {e}")
                self.modal_available = False

        # 6. HuggingFace
        if getattr(settings, "HUGGINGFACEHUB_API_TOKEN", None):
            try:
                print("🤗 [Level 6] HuggingFace (Async Fallback)")
                return await self.huggingface.ainvoke(safe_messages, config=config, **kwargs)
            except Exception as e:
                print(f"❌ HuggingFace Failed: {e}")

        raise RuntimeError("所有模型均不可使用或呼叫失敗，請檢查 API Keys 或帳戶額度。")

    def reset(self):
        """恢復所有模型可用狀態"""
        self.gemini_available = True
        self.groq_available = True
        self.siliconflow_available = True
        self.openrouter_available = True
        self.modal_available = True


router = LLMRouter()