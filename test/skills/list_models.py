import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

print("=== 所有可用模型 ===")
for m in client.models.list():
    print(m.name, "->", m.supported_actions)

print("\n=== 只看支持 embedContent 的模型 ===")
for m in client.models.list():
    if "embedContent" in (m.supported_actions or []):
        print(m.name)