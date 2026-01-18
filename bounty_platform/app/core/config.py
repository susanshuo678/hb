import os

class Settings:
    SECRET_KEY: str = os.getenv("SECRET_KEY", "bounty_secret_key_v3")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    
    # 数据库配置
    DATABASE_URL: str = os.getenv("DATABASE_URL", "mysql+pymysql://root:root_password_ChangeMe!@db/bounty_db")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379/0")

settings = Settings()