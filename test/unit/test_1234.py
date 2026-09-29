#!/usr/bin/env python3
"""
LM Studio 调试转发代理
----------------------
把 Roo Code (或任何 OpenAI 兼容客户端) 的请求原样转发给真实的 LM Studio 服务器，
同时把完整的请求体、响应体、状态码、耗时都打印出来，方便定位问题。

用法：
    pip install aiohttp
    python lmstudio_debug_proxy.py

默认：
    本地监听端口: 8888
    转发目标:     http://192.168.5.25:1234

然后把 Roo Code 里 LM Studio 的 Base URL 改成:
    http://localhost:8888/v1

（不需要改任何其他设置，代理会把 /v1/xxx 原样转发到真实服务器的 /v1/xxx）

所有日志会打印在终端，同时也会写入同目录下的 lmstudio_proxy.log 文件，
方便事后翻查、或者直接把日志文件贴给别人帮忙分析。
"""

import asyncio
import json
import logging
import time
from datetime import datetime

from aiohttp import web, ClientSession, ClientTimeout

# ========== 配置区，按需修改 ==========
LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = 8888
TARGET_BASE_URL = "http://192.168.5.25:1234"  # 真实 LM Studio 地址
LOG_FILE = "lmstudio_proxy.log"
# 请求体、响应体日志最多打印多少字符，避免刷屏（完整内容仍会写入日志文件）
MAX_LOG_CHARS_CONSOLE = 500000
# =====================================

# 同时输出到终端和文件
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
log = logging.getLogger("lmstudio_proxy")


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n...[truncated, total {len(text)} chars]..."


async def handle_proxy(request: web.Request) -> web.Response:
    path = request.path
    target_url = f"{TARGET_BASE_URL}{path}"
    if request.query_string:
        target_url += f"?{request.query_string}"

    body_bytes = await request.read()
    req_id = f"{int(time.time() * 1000)}"
    start_ts = time.monotonic()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ---- 打印请求 ----
    log.info("=" * 80)
    log.info(f"[{now_str}] >>> REQUEST  id={req_id}")
    log.info(f"  {request.method} {target_url}")
    try:
        pretty_body = json.dumps(json.loads(body_bytes), ensure_ascii=False, indent=2)
    except Exception:
        pretty_body = body_bytes.decode("utf-8", errors="replace")
    log.info(_truncate(pretty_body, MAX_LOG_CHARS_CONSOLE))

    # 转发用的 headers：去掉 Host，避免和目标服务器冲突
    fwd_headers = {k: v for k, v in request.headers.items() if k.lower() != "host"}

    timeout = ClientTimeout(total=None)  # 不限制超时，完整等待 LM Studio 返回
    try:
        async with ClientSession(timeout=timeout) as session:
            async with session.request(
                request.method,
                target_url,
                headers=fwd_headers,
                data=body_bytes,
            ) as resp:
                resp_bytes = await resp.read()
                elapsed = time.monotonic() - start_ts

                # ---- 打印响应 ----
                log.info(f"[{now_str}] <<< RESPONSE id={req_id}  "
                         f"status={resp.status}  elapsed={elapsed:.2f}s")
                try:
                    pretty_resp = json.dumps(
                        json.loads(resp_bytes), ensure_ascii=False, indent=2
                    )
                except Exception:
                    pretty_resp = resp_bytes.decode("utf-8", errors="replace")
                log.info(_truncate(pretty_resp, MAX_LOG_CHARS_CONSOLE))
                log.info("=" * 80 + "\n")

                # 把响应原样透传回客户端
                out_headers = {
                    k: v
                    for k, v in resp.headers.items()
                    if k.lower() not in ("content-encoding", "transfer-encoding", "content-length")
                }
                return web.Response(
                    body=resp_bytes,
                    status=resp.status,
                    headers=out_headers,
                )
    except asyncio.CancelledError:
        elapsed = time.monotonic() - start_ts
        log.info(f"[{now_str}] !!! CANCELLED id={req_id}  "
                 f"客户端中途断开/取消了请求，elapsed={elapsed:.2f}s")
        log.info("=" * 80 + "\n")
        raise
    except Exception as e:
        elapsed = time.monotonic() - start_ts
        log.info(f"[{now_str}] !!! ERROR id={req_id}  "
                 f"elapsed={elapsed:.2f}s  error={type(e).__name__}: {e}")
        log.info("=" * 80 + "\n")
        return web.json_response(
            {"error": {"type": type(e).__name__, "message": str(e)}},
            status=502,
        )


def main():
    app = web.Application()
    app.router.add_route("*", "/{path:.*}", handle_proxy)

    log.info(f"LM Studio 调试代理已启动")
    log.info(f"  本地监听: http://{LISTEN_HOST}:{LISTEN_PORT}")
    log.info(f"  转发目标: {TARGET_BASE_URL}")
    log.info(f"  日志文件: {LOG_FILE}")
    log.info(f"  把 Roo Code 的 LM Studio Base URL 改成: http://localhost:{LISTEN_PORT}/v1\n")

    web.run_app(app, host=LISTEN_HOST, port=LISTEN_PORT, print=None)


if __name__ == "__main__":
    main()