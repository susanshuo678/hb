from passlib.context import CryptContext
from datetime import datetime, timedelta
from typing import Optional

# 1. 密码加密配置
# 【修改点】我们将 schemes 改为 "pbkdf2_sha256"，这更稳定，不会报错
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

# --- 核心功能 A: 验证密码 ---
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

# --- 核心功能 B: 加密密码 ---
def get_password_hash(password):
    return pwd_context.hash(password)