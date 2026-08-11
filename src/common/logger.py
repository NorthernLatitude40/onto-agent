import logging
import sys
import os

# 1. 声明标准的日志输出格式
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(log_level: str = None) -> None:
    """
    全局日志统一初始化函数
    在应用启动时只需要调用一次，即可接管包含 FastAPI、Uvicorn 在内的全局日志
    """
    if log_level is None:
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    numeric_level = getattr(logging, log_level, logging.INFO)

    # 2. 清理现有的 Handlers，防止重复添加导致的日志重复打印
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # 3. 创建统一输出到控制台的 StreamHandler
    # 强制使用 sys.stdout 确保 Docker/Render 日志即时输出不卡缓存
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(
        logging.Formatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT)
    )

    # 4. 配置根日志记录器 (Root Logger)
    root_logger.setLevel(numeric_level)
    root_logger.addHandler(console_handler)

    # 5. 💡 关键：统一步调，让 Uvicorn 的日志也使用我们定义的格式
    for logger_name in ("uvicorn", "uvicorn.access", "uvicorn.error", "fastapi"):
        uv_logger = logging.getLogger(logger_name)
        uv_logger.handlers = []  # 移除 uvicorn 自带的格式化器
        uv_logger.propagate = True  # 向上传递给 Root Logger 统一处理


def get_logger(name: str) -> logging.Logger:
    """
    获取带模块名称的 Logger 实例（业务代码中统一调用这个）
    """
    return logging.getLogger(name)