import asyncio
import json
import os
import threading
import traceback
import aiohttp
import discord
import gradio as gr
import spaces

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
            timeout=aiohttp.ClientTimeout(total=180)
        ) as resp:

            if resp.status != 200:
                await message.channel.send(f"错误：后端服务返回了状态码 {resp.status}")
                return

            full_reply = ""
            async for line in resp.content:
                line_str = line.decode('utf-8').strip()
                if line_str.startswith("data:"):
                    res = line_str[5:].strip()
                    try:
                        data = json.loads(res)
                        if "content" in data:
                            content = data["content"]
                            # 安全解析 JSON 並取值
                            if isinstance(content, str) and content.strip().startswith("{"):
                                content_res = json.loads(content)
                                if isinstance(content_res, dict) and "reply" in content_res:
                                    full_reply = content_res["reply"]  # 注意：原本程式碼中的 data 應更正為 content_res
                            else:
                                # 原始內容不是 JSON 格式時的處理
                                full_reply = content
                    except json.JSONDecodeError:
                        full_reply += content

            if not full_reply:
                full_reply = "抱歉，我没有收到有效的回复内容。"

            for i in range(0, len(full_reply), 1900):
                await message.channel.send(full_reply[i:i+1900])

    except Exception as e:
        print(f"❌ [on_message] 请求异常: {e}")
        traceback.print_exc()
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


# --- 3. 占位 GPU 函数 ---
# 本应用完全不需要 GPU（纯 Discord Bot + 状态页），但当前账号被 HF 强制分配了
# ZeroGPU 硬件，其 `spaces` 库要求启动时至少检测到一个 @spaces.GPU 装饰的函数，
# 否则直接报 "No @spaces.GPU function detected during startup"。这里放一个
# 从不会被实际调用的占位函数，仅用于通过这项启动检查。
@spaces.GPU
def _zerogpu_placeholder():
    return "ok"


# --- 4. Gradio 状态页面 (满足 Hugging Face 的健康检查协议) ---
def get_status():
    if client.is_ready():
        return f"🟢 Online: {client.user}"
    return "🟡 Connecting..."

with gr.Blocks(title="Discord Bot Service") as demo:
    gr.Markdown("## 🤖 Discord Bot Service")
    status_box = gr.Textbox(label="Status", value=get_status, every=5)


if __name__ == "__main__":
    start_bot_once()
    demo.queue()
    demo.launch(server_name="0.0.0.0", server_port=7860, ssr_mode=False)