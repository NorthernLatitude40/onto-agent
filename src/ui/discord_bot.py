import discord
import aiohttp
import asyncio
from src.config.config import DISCORD_TOKEN, AGENT_SERVER_URL

TOKEN = DISCORD_TOKEN

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

# 创建一个全局的 aiohttp 会话，避免重复创建
session = None

@client.event
async def on_ready():
    global session
    session = aiohttp.ClientSession()
    print(f'Logged in as {client.user}')

@client.event
async def on_message(message):
    if message.author.bot:
        return

    # 异步请求
    async with session.post(
        AGENT_SERVER_URL + "/api/v1/chat",
        json={"user_id": str(message.author.id), "message": message.content}
    ) as resp:
        
        # 1. 检查状态码
        if resp.status != 200:
            await message.channel.send(f"错误：后端服务返回了状态码 {resp.status}")
            return

        # 2. 处理流式响应 (SSE格式: data: {...})
        # 我们需要读取每一行，找到并提取 JSON 数据
        full_reply = ""
        async for line in resp.content:
            line = line.decode('utf-8').strip()
            if line.startswith("data:"):
                # 获取数据部分
                content = line[5:].strip()
                # 如果内容包含 JSON，尝试解析
                try:
                    import json
                    data = json.loads(content)
                    if "reply" in data:
                        full_reply = data["reply"]
                except (json.JSONDecodeError, Exception):  # ✅ 指定明確的 Exception
                    # 如果不是 JSON（比如只是纯文本回复），直接追加
                    full_reply += content

        # 3. 发送最终回复
        if full_reply:
            await message.channel.send(full_reply)
        else:
            await message.channel.send("抱歉，我没有收到有效的回复内容。")

# 记得在程序退出时关闭 session
try:
    client.run(TOKEN)
finally:
    if session:
        asyncio.run(session.close())