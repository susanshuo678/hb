from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import redis.asyncio as redis
import os

# MySQL 配置
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./bounty.db")

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=20,          # 连接池大小
    max_overflow=10,       # 超出缓冲
    pool_recycle=3600      # 连接回收时间
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Redis 配置 (用于限流和缓存)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_conn = redis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()