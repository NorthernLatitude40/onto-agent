from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from src.config.config import settings

# ----------------------------------------------------
# 同步引擎（create_engine 是惰性的，匯入時不會真的連線）
# ----------------------------------------------------
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    echo=settings.is_development,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


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


def init_db() -> None:
    """
    建立資料表（如果不存在）。
    只在應用啟動時呼叫（見 main.py 的 lifespan），不要在模組層級執行，
    否則任何 import 這個模組的地方（包含單元測試）都會連上真實資料庫。
    正式環境建議改用 Alembic 管理 schema。
    """
    # 確保所有 model 都已被匯入並註冊到 Base.metadata
    # （若各 model 在別處已被匯入，這裡可省略）
    Base.metadata.create_all(bind=engine)


# ----------------------------------------------------
# 非同步引擎
# ----------------------------------------------------
engine_async = create_async_engine(
    settings.DATABASE_URL_ASYNC,
    echo=settings.is_development,
    connect_args={
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
    },
)
AsyncSessionLocal = async_sessionmaker(
    engine_async, class_=AsyncSession, expire_on_commit=False
)


# get_db_async 需為非同步產生器
async def get_db_async():
    async with AsyncSessionLocal() as session:
        yield session