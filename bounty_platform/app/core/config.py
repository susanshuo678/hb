import os

class Settings:
    PROJECT_NAME: str = "红白悬赏 V3 Enterprise"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your_super_secret_key_change_this_in_prod")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7天过期

    # Redis 配置
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # 路径配置
    UPLOAD_DIR: str = os.path.join(os.getcwd(), "app/static/uploads")

settings = Settings()