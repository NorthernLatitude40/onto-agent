# redis_client.py
import os
import redis

# 从 Render 的环境变量中读取 Redis 地址
REDIS_URL = os.getenv("REDIS_URL", "redis://:password123@localhost:6379/0")

# 创建 redis 连接池
redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)