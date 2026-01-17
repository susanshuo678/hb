from fastapi import APIRouter, Depends, Response, Request, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from ..database import get_db
from ..core import security
from .. import models

router = APIRouter(tags=["Auth"])
templates = Jinja2Templates(directory="app/templates")

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/login")
def login(response: Response, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user or not security.verify_password(password, user.hashed_password):
        return {"code": 400, "message": "账号或密码错误"}
    if user.is_banned: return {"code": 403, "message": "账号被封禁"}
    
    token = security.create_access_token({"sub": user.username})
    response = RedirectResponse(url="/admin/dashboard" if user.is_admin else "/h5/index", status_code=302)
    response.set_cookie(key="access_token", value=f"Bearer {token}", httponly=True)
    return response

@router.get("/logout")
def logout():
    resp = RedirectResponse(url="/login")
    resp.delete_cookie("access_token")
    return resp