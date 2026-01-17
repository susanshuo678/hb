from fastapi import APIRouter, Depends, Form, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models
from ..core import deps
import json

router = APIRouter(prefix="/admin", tags=["Admin"])
templates = Jinja2Templates(directory="app/templates")

# 1. 用户管理 (含封号)
@router.post("/users/ban")
def ban_user(
    user_id: int = Form(...),
    action: str = Form(...), # 'ban' or 'unban'
    admin_user: models.User = Depends(deps.get_current_admin),
    db: Session = Depends(get_db)
):
    target = db.query(models.User).filter(models.User.id == user_id).first()
    if not target: return {"code": 404, "message": "用户不存在"}
    
    target.is_banned = (action == "ban")
    
    # 记录审计日志
    audit = models.AuditLog(
        operator_id=admin_user.id,
        action="ban_user" if action == "ban" else "unban_user",
        target_id=user_id,
        detail=json.dumps({"username": target.username}),
        ip_address="127.0.0.1" # 实际应从 Request 获取
    )
    db.add(audit)
    db.commit()
    return {"code": 200, "message": "操作成功"}

# 2. 申诉处理 (复审)
@router.post("/appeal/resolve")
def resolve_appeal(
    sub_id: int = Form(...),
    result: str = Form(...), # 'pass' or 'reject'
    admin_user: models.User = Depends(deps.get_current_admin),
    db: Session = Depends(get_db)
):
    sub = db.query(models.Submission).filter(models.Submission.id == sub_id).first()
    if not sub: return {"code": 404, "message": "订单不存在"}
    
    if result == "pass":
        sub.status = "approved"
        # 发钱逻辑省略，建议封装在 Service
        sub.user.balance += sub.task.price # 简单示例
    else:
        sub.status = "rejected"
        sub.admin_feedback = "申诉驳回: 证据不足"
        
    db.commit()
    return {"code": 200, "message": "处理完毕"}

# 3. 审计日志列表
@router.get("/audit_logs")
def view_audit_logs(
    request: Request,
    page: int = 1,
    admin_user: models.User = Depends(deps.get_current_admin),
    db: Session = Depends(get_db)
):
    limit = 20
    offset = (page - 1) * limit
    logs = db.query(models.AuditLog).order_by(models.AuditLog.created_at.desc()).offset(offset).limit(limit).all()
    return templates.TemplateResponse("admin/audit_logs.html", {"request": request, "logs": logs, "user": admin_user})