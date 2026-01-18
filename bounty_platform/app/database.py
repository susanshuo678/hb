import redis.asyncio as redis
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from .core.config import settings

# 1. MySQL 配置 (同步，用于业务逻辑)
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=30,
    pool_recycle=3600,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 2. Redis 配置 (异步，用于限流和缓存)
redis_conn = redis.from_url(
    settings.REDIS_URL,
    encoding="utf-8",
    decode_responses=True,
    socket_connect_timeout=5
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()