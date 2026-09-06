import asyncio
import json
import os
import threading
import traceback
import aiohttp
import discord
import gradio as gr
from src.config.config import settings

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
    print(f'✅ Discord Bot 成功登录: {client.user}')

@client.event
async def on_message(message):
    if message.author.bot:
        return

    try:
        agent_url = getattr(settings, "AGENT_SERVER_URL", None) or os.getenv("AGENT_SERVER_URL", "")
        if not agent_url:
            await message.channel.send("错误：未配置 AGENT_SERVER_URL 环境变量。")
            return

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


# --- 2. 后台线程启动 Discord Bot ---
def run_bot():
    token = getattr(settings, "DISCORD_TOKEN", None) or os.getenv("DISCORD_TOKEN", "")
    if not token:
        print("❌ 错误：环境变量 DISCORD_TOKEN 未配置，Bot 无法启动！")
        return

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        print("🚀 正在启动 Discord Bot...")
        loop.run_until_complete(client.start(token))
    except Exception as e:
        print(f"❌ Bot 运行崩溃: {e}")
        traceback.print_exc()

# 启动后台线程
bot_thread = threading.Thread(target=run_bot, daemon=True)
bot_thread.start()


# --- 3. Gradio 保活界面 (供 Hugging Face 检测 7860 端口) ---
with gr.Blocks(title="Discord Bot Host") as demo:
    gr.Markdown("# 🤖 Discord Bot Web Service")
    gr.Markdown("✅ 服务正在稳定运行中...")

if __name__ == "__main__":
    # 关键设置：
    # 1. server_name="0.0.0.0" 让容器能够监听到外部请求
    # 2. block=True（默认值）确保主线程挂起，防止程序直接退出导致 Stopping Node.js server
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        show_error=True
    )