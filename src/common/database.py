import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, BigInteger, String, Numeric, DateTime, func
from sqlalchemy.orm import declarative_base, sessionmaker
from src.config.config import settings
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from src.config.config import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, echo=settings.is_development)
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


engine_async = create_async_engine(
        settings.DATABASE_URL_ASYNC, 
        echo=True,
        connect_args={
            "statement_cache_size": 0,
            "prepared_statement_cache_size": 0
        }
    )
AsyncSessionLocal = async_sessionmaker(engine_async, class_=AsyncSession, expire_on_commit=False)

# 2. get_db 需為非同步產生器
async def get_db_async():
    async with AsyncSessionLocal() as session:
        yield session