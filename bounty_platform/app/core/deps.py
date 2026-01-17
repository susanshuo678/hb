from fastapi import Depends, HTTPException, status, Request
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models
from .config import settings

async def get_current_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token: return None
    try:
        if token.startswith("Bearer "): token = token.split(" ")[1]
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None: return None
    except JWTError: return None

    user = db.query(models.User).filter(models.User.username == username).first()
    # 🚫 V3: 黑名单拦截
    if user and user.is_banned:
        raise HTTPException(status_code=403, detail="账号已被封禁")
    return user

async def get_current_active_user(user: models.User = Depends(get_current_user)):
    if not user: raise HTTPException(status_code=401, detail="未登录")
    return user

async def get_current_admin(user: models.User = Depends(get_current_active_user)):
    if not user.is_admin: raise HTTPException(status_code=403, detail="权限不足")
    return user