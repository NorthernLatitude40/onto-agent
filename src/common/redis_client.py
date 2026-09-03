# redis_client.py
import os
import redis

# 从 Render 的环境变量中读取 Redis 地址
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# 创建 Redis 连接池并配置网络心跳与超时保护
redis_client = redis.Redis.from_url(
    REDIS_URL,
    decode_responses=True,
    socket_timeout=30,  # 单次 Socket 读写超时时间（秒）
    socket_keepalive=True,  # 开启 TCP Keepalive 机制，防止长连接被防火墙/云平台断开
    health_check_interval=30,  # 每 30 秒自动发送 PING 检查连接健康度，断线自动重连
)