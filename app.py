import asyncio
import json
import os
import threading
import traceback
import aiohttp
import discord
from http.server import HTTPServer, BaseHTTPRequestHandler

# 延迟读取 settings
def get_settings():
    try:
        from src.config.config import settings
        return settings
    except Exception as e:
        print(f"⚠️ 读取 settings 失败: {e}")
        return None

# --- 1. Discord Bot 核心逻辑 ---
intents = discord.Intents.default()
intents.message_content = True

class MyBot(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session = None

    async def setup_hook(self):
        self.session = aiohttp.ClientSession()

    async def close(self):
        if self.session:
            await self.session.close()
        await super().close()

client = MyBot(intents=intents)

@client.event
async def on_ready():
    print(f'🎉🎉🎉 [SUCCESS] Discord Bot 成功登录上线: {client.user}')

@client.event
async def on_message(message):
    if message.author.bot:
        return

    settings = get_settings()
    agent_url = getattr(settings, "AGENT_SERVER_URL", None) or os.getenv("AGENT_SERVER_URL", "")

    if not agent_url:
        await message.channel.send("错误：未配置 AGENT_SERVER_URL 环境变量。")
        return

    try:
        async with client.session.post(
            agent_url.rstrip("/") + "/api/v1/chat",
            json={"user_id": str(message.author.id), "message": message.content},
            timeout=aiohttp.ClientTimeout(total=60)
        ) as resp:

            if resp.status != 200:
                await message.channel.send(f"错误：后端服务返回了状态码 {resp.status}")
                return

            full_reply = ""
            async for line in resp.content:
                line_str = line.decode('utf-8').strip()
                if line_str.startswith("data:"):
                    content = line_str[5:].strip()
                    try:
                        data = json.loads(content)
                        if "reply" in data:
                            full_reply = data["reply"]
                    except json.JSONDecodeError:
                        full_reply += content

            if not full_reply:
                full_reply = "抱歉，我没有收到有效的回复内容。"

            for i in range(0, len(full_reply), 1900):
                await message.channel.send(full_reply[i:i+1900])

    except Exception as e:
        await message.channel.send(f"服务请求异常: {str(e)}")


# --- 2. 进程级单例 Bot 启动器 ---
# 用 os.environ 而不是模块内的 bool 变量做标记：
# os.environ 是整个进程共享的，即使这个模块文件被 import/reload 多次
# （产生多个独立的模块命名空间），也不会重复启动 bot。
def start_bot_once():
    if os.environ.get("_DISCORD_BOT_STARTED") == "1":
        print("⚠️ 检测到 Bot 已启动过，跳过本次启动")
        return
    os.environ["_DISCORD_BOT_STARTED"] = "1"

    settings = get_settings()
    token = getattr(settings, "DISCORD_TOKEN", None) or os.getenv("DISCORD_TOKEN", "")

    if not token:
        print("❌ 错误：环境变量 DISCORD_TOKEN 未配置，Bot 无法启动！")
        return

    print("🔑 正在拉起唯一的 Discord Bot 后台线程...")

    def run_bot():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(client.start(token))
        except Exception as e:
            print(f"❌ Bot 运行发生异常: {e}")
            traceback.print_exc()

    thread = threading.Thread(target=run_bot, daemon=True)
    thread.start()


# --- 3. 原生 HTTP 保活服务器 (满足 Hugging Face 7860 健康检查) ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        status_text = f"🟢 Online: {client.user}" if client.is_ready() else "🟡 Connecting..."
        html = f"<h1>🤖 Discord Bot Service</h1><p>Status: {status_text}</p>"
        self.wfile.write(html.encode("utf-8"))

    def log_message(self, format, *args):
        # 屏蔽心跳日志，保持控制台输出干净
        return


if __name__ == "__main__":
    # bot 启动也收进 __main__，避免被其他模块 import 时被意外触发
    start_bot_once()
    server = HTTPServer(("0.0.0.0", 7860), HealthCheckHandler)
    print("🚀 7860 端口心跳服务器已就绪...")
    server.serve_forever()