import os
from functools import lru_cache
from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    """
    全局应用配置管理
    优先读取环境变量，其次读取 .env 文件，最后回退到 default 值
    """

    # --- 环境标记 ---
    # 支持 development / production / test 等
    ENV: Literal["development", "production", "test"] = "development"

    # --- AI / LLM 服务 API Keys ---
    GEMINI_API_KEY: str | None = None
    OPENROUTER_API_KEY: str | None = None
    HUGGINGFACEHUB_API_TOKEN: str | None = Field(default=None, alias="HUGGING_FACE_API_KEY")

    # --- Agent & 服务连接地址 ---
    AGENT_SERVER_URL: str | None = None

    # --- AnythingLLM 配置 ---
    ANYTHINGLLM_BASE_URL: str = "http://localhost:3001/api/v1"
    ANYTHINGLLM_API_KEY: str = "xxxxx"  # 建议写在 .env 中，此处仅作为本地开发默认值
    WORKSPACE_SLUG: str = "ticketrules"

    # --- 可观测性 / Langfuse 配置 ---
    ENABLE_LANGFUSE: bool = True

    # --- 第三方平台集成 ---
    DISCORD_TOKEN: str | None = None
    WX_APP_ID: str | None = None
    WX_APP_SECRET: str | None = None
    JWT_SECRET_KEY: str = "change_this_to_a_secure_secret_in_prod"

    # ----------------------------------------------------------------------
    # 配置与路径常量（禁止硬编码本地绝对路径）
    # ----------------------------------------------------------------------
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    UPLOAD_DIR: Path = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "uploads"))
    EXPORTS_DIR: Path = Path(os.getenv("EXPORTS_DIR", BASE_DIR / "exports"))



    # --- Pydantic Settings 配置项 ---
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # 忽略 .env 中未定义的多余变量
        case_sensitive=True,
    )

    # --- 快捷属性 / 逻辑派生 ---
    @property
    def is_production(self) -> bool:
        return self.ENV == "production"

    @property
    def is_development(self) -> bool:
        return self.ENV == "development"

    def setup_global_env_vars(self) -> None:
        """
        初始化全局必要的环境变量依赖 (例如 Langfuse / OpenTelemetry)
        必须在创建任何 Langfuse 实例之前调用
        """
        os.environ["LANGFUSE_TRACING_ENABLED"] = "True" if self.ENABLE_LANGFUSE else "False"


# 使用 lru_cache 确保全局单例，避免重复读取 .env 文件的磁盘开销
@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    # 实例化时自动注入必要的全局环境变量
    settings.setup_global_env_vars()
    return settings


# 导出全局可直接调用的对象
settings = get_settings()