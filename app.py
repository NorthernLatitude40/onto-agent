import asyncio
import json
import os
import threading
import traceback
import aiohttp
import discord
import gradio as gr

# 彻底延迟导入 settings，防止 config.py 初始化时数据库连接卡死进程
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


# --- 2. 延迟 5 秒启动 Bot（让 Gradio 先握手成功） ---
def run_bot_delayed():
    import time
    print("⏳ 等待 5 秒，优先让 Gradio 响应 Hugging Face 健康检查...")
    time.sleep(5)
    
    settings = get_settings()
    token = getattr(settings, "DISCORD_TOKEN", None) or os.getenv("DISCORD_TOKEN", "")
    
    if not token:
        print("❌ 错误：环境变量 DISCORD_TOKEN 未配置，Bot 无法启动！")
        return

    print(f"🔑 读取到 Token 长度: {len(token)}，开始连接 Discord...")
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def start_bot():
        try:
            print("🚀 正在发起 Discord WebSocket 连接...")
            await client.start(token)
        except discord.errors.LoginFailure:
            print("❌ 致命错误：Discord Token 无效！请检查 Secrets 里的 DISCORD_TOKEN（注意两端不要加引号或空格）。")
        except discord.errors.PrivilegedIntentsRequired:
            print("❌ 致命错误：缺少 Privileged Gateway Intent 权限！")
        except Exception as e:
            print(f"❌ Bot 运行发生未知异常: {e}")
            traceback.print_exc()

    loop.run_until_complete(start_bot())

# 启动后台线程（Daemon=True 保证主进程退时跟退，但由 Gradio 保活）
bot_thread = threading.Thread(target=run_bot_delayed, daemon=True)
bot_thread.start()


# --- 3. Gradio 保活界面 ---
with gr.Blocks(title="Discord Bot Host") as demo:
    gr.Markdown("# 🤖 Discord Bot Web Service")
    gr.Markdown("✅ 服务正在稳定运行中...")

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        show_error=True
    )