from fastapi import APIRouter, Depends, Form, Request, UploadFile, File
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
import json, io
import openpyxl

from ..database import get_db
from .. import models
from ..core import deps
from ..services.risk_control import save_upload_file_sync

router = APIRouter(prefix="/admin", tags=["Admin"])
templates = Jinja2Templates(directory="app/templates")

# 1. 看板
@router.get("/dashboard")
def dashboard(request: Request, db: Session = Depends(get_db), user=Depends(deps.get_current_admin)):
    stats = {
        "pending_audit": db.query(models.Submission).filter(models.Submission.status == "pending").count(),
        "users": db.query(models.User).count(),
        "active_tasks": db.query(models.Task).filter(models.Task.is_active == True).count(),
        "pending_withdraw": db.query(models.Withdrawal).filter(models.Withdrawal.status == "pending").count()
    }
    return templates.TemplateResponse("admin/dashboard.html", {
        "request": request, "user": user, "stats": stats, 
        "chart_dates": [], "chart_users": [], "chart_subs": [], "chart_money": []
    })

# 2. 会员管理
@router.get("/users")
def admin_users(request: Request, db: Session = Depends(get_db), user=Depends(deps.get_current_admin)):
    users = db.query(models.User).order_by(models.User.created_at.desc()).limit(100).all()
    return templates.TemplateResponse("admin/user_list.html", {"request": request, "users": users, "user": user})

@router.post("/users/balance")
def admin_user_balance(user_id: int = Form(...), amount: float = Form(...), db: Session = Depends(get_db)):
    u = db.query(models.User).filter(models.User.id == user_id).first()
    if u: 
        u.balance += amount
        db.commit()
    return RedirectResponse("/admin/users", status_code=302)

@router.post("/users/ban")
def ban_user(user_id: int = Form(...), action: str = Form(...), db: Session = Depends(get_db), user=Depends(deps.get_current_admin)):
    u = db.query(models.User).filter(models.User.id == user_id).first()
    if u:
        u.is_banned = (action == "ban")
        db.commit()
    return {"code": 200, "message": "操作成功"}

# 3. 任务审核
@router.get("/audit")
def admin_audit(request: Request, db: Session = Depends(get_db), user=Depends(deps.get_current_admin)):
    subs = db.query(models.Submission).filter(models.Submission.status == "pending").all()
    return templates.TemplateResponse("admin/audit.html", {"request": request, "submissions": subs, "user": user})

@router.post("/audit/review")
def admin_review(submission_id: int = Form(...), action: str = Form(...), feedback: str = Form(None), amount: float = Form(0.0), db: Session = Depends(get_db)):
    sub = db.query(models.Submission).filter(models.Submission.id == submission_id).first()
    if not sub: return RedirectResponse("/admin/audit", status_code=302)
    
    if action == "approve":
        reward = amount if sub.task.price_mode == 'dynamic' else sub.task.price
        sub.status = "approved"
        sub.user.balance += reward
        sub.final_amount = reward
        # 简单处理返佣
        if sub.user.inviter_id:
            inviter = db.query(models.User).filter(models.User.id == sub.user.inviter_id).first()
            if inviter: inviter.balance += reward * 0.1
    else:
        sub.status = "rejected"
        sub.admin_feedback = feedback
        
    db.commit()
    return RedirectResponse("/admin/audit", status_code=302)

# 4. 发布任务
@router.get("/task/new")
def admin_task_new(request: Request, db: Session = Depends(get_db), user=Depends(deps.get_current_admin)):
    cats = db.query(models.TaskCategory).all()
    mat_cats = db.query(models.MaterialCategory).all()
    return templates.TemplateResponse("admin/task_edit.html", {
        "request": request, "categories": cats, "mat_categories": mat_cats, "user": user
    })

@router.post("/task/new")
def admin_task_create(title: str = Form(...), price: float = Form(0), category: str = Form(...), description: str = Form(...), db: Session = Depends(get_db)):
    db.add(models.Task(title=title, price=price, category=category, description=description))
    db.commit()
    return RedirectResponse("/admin/dashboard", status_code=302)

# 5. 设置页
@router.get("/settings")
def admin_settings(request: Request, db: Session = Depends(get_db), user=Depends(deps.get_current_admin)):
    return templates.TemplateResponse("admin/settings.html", {"request": request, "user": user, "banners": db.query(models.Banner).all(), "categories": db.query(models.TaskCategory).all(), "announcement": "", "pay_qrcode": "", "commission_rate": 10})