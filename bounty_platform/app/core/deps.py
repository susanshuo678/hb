from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.config import settings
from app.database import get_db
from app.models import User

class TokenData(BaseModel):
    username: Optional[str] = None

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# 1. 基础验证
async def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭证",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    
    user = db.query(User).filter(User.username == token_data.username).first()
    if user is None:
        raise credentials_exception
    return user

# 2. 活跃用户验证 (修复 user.py 报错)
async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.is_banned:
        raise HTTPException(status_code=400, detail="您的账号已被封禁")
    return current_user

# 3. 管理员验证 (核心修复点)
async def get_current_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="权限不足，仅限管理员操作"
        )
    return current_user
    
# 财务专用 (只看钱)
async def get_current_finance_admin(current_user: User = Depends(get_current_user)):
    # 假设 admin 表里加个 role 字段，或者简单粗暴判断
    # 这里我们演示：只要是管理员都能进，但在 router 里做逻辑区分
    # V3 进阶：建议在 User 表增加 role 字段: 'super', 'finance', 'audit'
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    # 如果要严格区分：
    # if current_user.role not in ['super', 'finance']: raise ...
    return current_user

# 审核专用 (只看单)
async def get_current_audit_admin(current_user: User = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return current_user

# 🟢 兼容别名：同时支持 get_current_admin 和 get_current_user_admin
# 这样 admin.py 和 material.py 就都不会报错了！
get_current_user_admin = get_current_admin