from fastapi import Depends, HTTPException, status, Request
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models
from .config import settings

# 从 Cookie 获取当前用户
async def get_current_user(request: Request, db: Session = Depends(get_db)) -> Optional[models.User]:
    token = request.cookies.get("access_token")
    if not token:
        return None
    
    try:
        # 去掉 'Bearer ' 前缀（如果有）
        if token.startswith("Bearer "):
            token = token.split(" ")[1]
            
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
    except JWTError:
        return None

    user = db.query(models.User).filter(models.User.username == username).first()
    
    # 🔴 V3核心：黑名单拦截
    if user and user.is_banned:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="该账号已被封禁，请联系客服。"
        )
        
    return user

# 必须登录
async def get_current_active_user(user: models.User = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user

# 必须是管理员
async def get_current_admin(user: models.User = Depends(get_current_active_user)):
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
    return user