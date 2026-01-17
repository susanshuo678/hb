from fastapi import APIRouter, Depends, status, Response, Request, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session
from fastapi.templating import Jinja2Templates
from ..database import get_db
from ..core import security, deps
from .. import models
import random, string

router = APIRouter(tags=["Auth"])
templates = Jinja2Templates(directory="app/templates")

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/login")
def login(
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user or not security.verify_password(password, user.hashed_password):
        return {"code": 400, "message": "账号或密码错误"}
    
    if user.is_banned:
         return {"code": 403, "message": "账号已封禁"}

    # 生成 JWT
    access_token = security.create_access_token(data={"sub": user.username})
    
    # 设置 Cookie
    response = RedirectResponse(url="/admin/dashboard" if user.is_admin else "/h5/index", status_code=302)
    response.set_cookie(key="access_token", value=f"Bearer {access_token}", httponly=True)
    return response

@router.get("/logout")
def logout(response: Response):
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("access_token")
    return response

@router.post("/register")
def register(
    username: str = Form(...),
    password: str = Form(...),
    invite_code: int = Form(None),
    db: Session = Depends(get_db)
):
    if db.query(models.User).filter(models.User.username == username).first():
        return {"code": 400, "message": "用户名已存在"}
    
    user = models.User(
        username=username,
        hashed_password=security.get_password_hash(password),
        inviter_id=invite_code
    )
    db.add(user)
    db.commit()
    return {"code": 200, "message": "注册成功"}