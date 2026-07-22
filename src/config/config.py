import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
HUGGINGFACEHUB_API_TOKEN = os.getenv("HUGGING_FACE_API_KEY")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

AGENT_SERVER_URL = os.getenv("AGENT_SERVER_URL")

ANYTHINGLLM_BASE_URL = "http://localhost:3001/api/v1"
ANYTHINGLLM_API_KEY = "xxxxx"
WORKSPACE_SLUG = "ticketrules"

ENABLE_LANGFUSE: bool = os.getenv("ENABLE_LANGFUSE", "true").lower() == "true"

# 关键：必须在创建任何 Langfuse 对象之前设置这个环境变量
# 它控制的是全局 OTEL TracerProvider,一旦设置,所有 CallbackHandler/Langfuse 实例都会遵守
os.environ["LANGFUSE_TRACING_ENABLED"] = "True" if ENABLE_LANGFUSE else "False"