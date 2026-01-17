import os
class Settings:
    SECRET_KEY: str = os.getenv("SECRET_KEY", "bounty_secret_key_v3")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
settings = Settings()