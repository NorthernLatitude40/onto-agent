import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
HUGGINGFACEHUB_API_TOKEN = os.getenv("HUGGING_FACE_API_KEY")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

ANYTHINGLLM_BASE_URL = "http://localhost:3001/api/v1"
ANYTHINGLLM_API_KEY = "xxxxx"
WORKSPACE_SLUG = "ticketrules"

MCP_SERVER_URL = "http://localhost:8001/sse"