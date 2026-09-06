import asyncio
import json
import os
import threading
import traceback
import aiohttp
import discord
import gradio as gr

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


# --- 2. 进程级别的单例防重复启动 ---
bot_started = False
bot_lock = threading.Lock()

def start_bot_once():
    global bot_started
    with bot_lock:
        if bot_started:
            return
        bot_started = True

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
            print(f"❌ Bot 运行异常: {e}")
            traceback.print_exc()

    thread = threading.Thread(target=run_bot, daemon=True)
    thread.start()

# 模块加载时立即尝试启动 Bot
start_bot_once()


# --- 3. Gradio 保活界面 ---
with gr.Blocks(title="Discord Bot Host") as demo:
    gr.Markdown("# 🤖 Discord Bot Web Service")
    gr.Markdown("✅ 服务正在稳定运行中...")

if __name__ == "__main__":
    # Gradio SDK 模式下最兼容的 launch 写法
    demo.launch()