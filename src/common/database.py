import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, BigInteger, String, Numeric, DateTime, func
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ----------------------------------------------------
# 🌟 就是这个 get_db 函数！FastAPI 路由依赖注入的核心
# ----------------------------------------------------
def get_db():
    """
    FastAPI 专用数据库 Session 生成器 (Yield)
    请求进来时创建 db，请求结束时自动 close()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# 自动创建表结构（如果表不存在）
Base.metadata.create_all(bind=engine)