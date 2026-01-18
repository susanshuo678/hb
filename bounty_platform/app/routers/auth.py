from fastapi import APIRouter, Depends, Response, Request, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from fastapi_limiter.depends import RateLimiter # 🟢 引入限流

from ..database import get_db
from ..core import security, logger
from .. import models

router = APIRouter(tags=["Auth"])
templates = Jinja2Templates(directory="app/templates")

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "user": None})

# 🟢 登录限流：每分钟最多试错 10 次
@router.post("/login", dependencies=[Depends(RateLimiter(times=10, seconds=60))])
def login(
    request: Request, 
    username: str = Form(...), 
    password: str = Form(...), 
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user or not security.verify_password(password, user.hashed_password):
        return templates.TemplateResponse("login.html", {
            "request": request, "error": "账号或密码错误", "user": None
        })
    
    if user.is_banned: 
        return templates.TemplateResponse("login.html", {
            "request": request, "error": "账号被封禁", "user": None
        })

    token = security.create_access_token({"sub": user.username})
    target_url = "/admin/dashboard" if user.is_admin else "/h5/index"
    resp = RedirectResponse(url=target_url, status_code=302)
    resp.set_cookie(key="access_token", value=f"Bearer {token}", httponly=True)
    return resp

@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request, invite: str = ""):
    return templates.TemplateResponse("register.html", {"request": request, "invite_code": invite, "user": None})

# 🟢 注册限流：每分钟最多 5 次 (防脚本批量注册)
@router.post("/register", dependencies=[Depends(RateLimiter(times=5, seconds=60))])
def register(
    request: Request,
    username: str = Form(...),
    password: str = Form(...), 
    captcha: str = Form(...),
    invite_code: str = Form(None),
    db: Session = Depends(get_db)
):
    session_captcha = request.session.get("captcha")
    if not session_captcha or str(session_captcha).lower() != captcha.lower():
        return templates.TemplateResponse("register.html", {
            "request": request, "error": "验证码错误", "invite_code": invite_code, "user": None
        })
    
    if db.query(models.User).filter(models.User.username == username).first():
        return templates.TemplateResponse("register.html", {
            "request": request, "error": "用户名已存在", "invite_code": invite_code, "user": None
        })

    hashed_pwd = security.get_password_hash(password)

    inviter_id = None
    if invite_code and invite_code.isdigit():
        inviter = db.query(models.User).filter(models.User.id == int(invite_code)).first()
        if inviter: inviter_id = inviter.id

    new_user = models.User(username=username, hashed_password=hashed_pwd, inviter_id=inviter_id)
    
    try:
        db.add(new_user)
        db.commit()
        request.session.pop("captcha", None)
        logger.logger.info(f"New user registered: {username}") # 记录日志
        return templates.TemplateResponse("register.html", {"request": request, "success": True, "user": None})
    except Exception as e:
        db.rollback()
        logger.logger.error(f"Register failed: {e}")
        return templates.TemplateResponse("register.html", {
            "request": request, "error": "注册失败，请联系管理员", "invite_code": invite_code, "user": None
        })

@router.get("/logout")
def logout():
    resp = RedirectResponse(url="/login")
    resp.delete_cookie("access_token")
    return resp