import copy
import json
import time
from typing import Any, List, Optional

import aiohttp
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
    timeout: float = 180.0

    @property
    def _llm_type(self) -> str:
        return "modal-qwen-chat"

    def _format_qwen_chatml(self, messages: List[BaseMessage]) -> str:
        """將 LangChain Messages 格式化為 Qwen2.5 標準 ChatML 模版"""
        prompt = ""
        for m in messages:
            if isinstance(m, SystemMessage):
                prompt += f"<|im_start|>system\n{m.content}<|im_end|>\n"
            elif isinstance(m, HumanMessage):
                prompt += f"<|im_start|>user\n{m.content}<|im_end|>\n"
            elif isinstance(m, AIMessage):
                prompt += f"<|im_start|>assistant\n{m.content}<|im_end|>\n"
            else:
                prompt += f"<|im_start|>user\n{m.content}<|im_end|>\n"
        prompt += "<|im_start|>assistant\n"
        return prompt

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """同步生成邏輯"""
        prompt = self._format_qwen_chatml(messages)
        stop_tokens = ["<|im_end|>", "<|endoftext|>"]
        if stop:
            stop_tokens.extend(stop)

        response = requests.post(
            self.endpoint_url,
            json={
                "prompt": prompt,
                "max_tokens": kwargs.get("max_tokens", 1024),
                "stop": stop_tokens,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()

        text = data.get("response", "").strip()
        for tag in stop_tokens:
            if text.endswith(tag):
                text = text[:-len(tag)].strip()

        message = AIMessage(content=text)
        return ChatResult(generations=[ChatGeneration(message=message)])

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """原生非阻塞非同步生成邏輯"""
        prompt = self._format_qwen_chatml(messages)
        stop_tokens = ["<|im_end|>", "<|endoftext|>"]
        if stop:
            stop_tokens.extend(stop)

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.endpoint_url,
                json={
                    "prompt": prompt,
                    "max_tokens": kwargs.get("max_tokens", 1024),
                    "stop": stop_tokens,
                },
                timeout=aiohttp.ClientTimeout(total=self.timeout),
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()

        text = data.get("response", "").strip()
        for tag in stop_tokens:
            if text.endswith(tag):
                text = text[:-len(tag)].strip()

        message = AIMessage(content=text)
        return ChatResult(generations=[ChatGeneration(message=message)])


# ===========================================================
# 2. LLMRouter 整合 Modal 兜底與完整 LangChain 介面
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

    # ===========================================================
    # 消息安全清洗
    # ===========================================================
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

    # ===========================================================
    # 模型介面與 Tool / Structured Output 支援
    # ===========================================================
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
        if self.modal_available:
            return self.modal_qwen
        return self.huggingface

    def get_num_tokens_from_messages(self, messages: list[BaseMessage]) -> int:
        """字符數估算 Token 兜底算法"""
        total_text = "".join([str(m.content) for m in messages if m and m.content])
        return max(1, len(total_text) // 2)

    def with_structured_output(self, schema: type[BaseModel]):
        """為支援的模型開啟 Structured Output"""
        for provider in ["gemini", "groq", "siliconflow", "openrouter", "modal_qwen", "huggingface"]:
            model_inst = getattr(self, provider, None)
            if model_inst and hasattr(model_inst, "with_structured_output"):
                try:
                    setattr(self, provider, model_inst.with_structured_output(schema))
                except Exception as e:
                    print(f"⚠️ {provider.capitalize()} 不支援 structured_output: {e}")
        return self

    def bind_tools(self, tools, **kwargs):
        """為各模型綁定 Tool，使用深拷貝防止多 Agent 交叉污染"""
        new_router = copy.copy(self)

        for provider in ["gemini", "groq", "siliconflow", "openrouter", "modal_qwen", "huggingface"]:
            model_inst = getattr(self, provider, None)
            if model_inst and hasattr(model_inst, "bind_tools"):
                try:
                    setattr(new_router, provider, model_inst.bind_tools(tools, **kwargs))
                except Exception:
                    pass

        return new_router

    # ===========================================================
    # 同步 & 異步 呼叫 (Invoke & Ainvoke)
    # ===========================================================
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
        if self.siliconflow_available and getattr(settings, "SILICONFLOW_API_KEY", None):
            try:
                print("🌊 [Level 3] Siliconflow")
                return self.siliconflow.invoke(safe_messages, config=config, **kwargs)
            except Exception as e:
                print(f"❌ Siliconflow Failed: {e}")
                self.siliconflow_available = False
                time.sleep(0.5)

        # 4. OpenRouter
        if self.openrouter_available and getattr(settings, "OPENROUTER_API_KEY", None):
            try:
                print("🚀 [Level 4] OpenRouter")
                return self.openrouter.invoke(safe_messages, config=config, **kwargs)
            except Exception as e:
                print(f"❌ OpenRouter Failed: {e}")
                self.openrouter_available = False
                time.sleep(0.5)

        # 5. Modal Qwen
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

        # 5. Modal Qwen (原生非阻塞 Async)
        if self.modal_available:
            try:
                print("☁️ [Level 5] Modal Private Qwen2.5 (Async)")
                return await self.modal_qwen.ainvoke(safe_messages, config=config, **kwargs)
            except Exception as e:
                print(f"❌ Modal Qwen Failed: {e}")
                self.modal_available = False

        # 6. HuggingFace
        if getattr(settings, "HUGGINGFACEHUB_API_TOKEN", None):
            try:
                print("🤗 [Level 6] HuggingFace (Async)")
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

    @property
    def status(self):
        return {
            "gemini": self.gemini_available,
            "groq": self.groq_available,
            "siliconflow": self.siliconflow_available,
            "openrouter": self.openrouter_available,
            "modal": self.modal_available,
            "huggingface": bool(getattr(settings, "HUGGINGFACEHUB_API_TOKEN", None)),
        }


router = LLMRouter()