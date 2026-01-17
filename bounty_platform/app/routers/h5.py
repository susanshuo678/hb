from fastapi import APIRouter, Depends, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from datetime import datetime
from ..database import get_db
from .. import models
from ..core import deps

router = APIRouter(prefix="/h5", tags=["H5"])
templates = Jinja2Templates(directory="app/templates")

# 1. 任务大厅
@router.get("/index")
def h5_index(request: Request, cat: str = "all", user = Depends(deps.get_current_active_user), db: Session = Depends(get_db)):
    query = db.query(models.Task).filter(models.Task.is_active == True)
    if cat != "all": query = query.filter(models.Task.category == cat)
    tasks = query.order_by(models.Task.id.desc()).all()
    
    banners = db.query(models.Banner).all()
    announcement = db.query(models.SystemConfig).filter(models.SystemConfig.key == "announcement").first()
    cats = db.query(models.TaskCategory).order_by(models.TaskCategory.sort_order.desc()).all()
    
    return templates.TemplateResponse("h5/index.html", {
        "request": request, "user": user, "tasks": tasks, 
        "banners": banners, "categories": cats, 
        "announcement": announcement.value if announcement else "", 
        "current_cat": cat
    })

# 2. 个人中心
@router.get("/mine")
def h5_mine(request: Request, user = Depends(deps.get_current_active_user), db: Session = Depends(get_db)):
    subs = db.query(models.Submission).filter(models.Submission.user_id == user.id).order_by(models.Submission.created_at.desc()).all()
    unread = db.query(models.Notification).filter(models.Notification.user_id == user.id, models.Notification.is_read == False).count()
    return templates.TemplateResponse("h5/mine.html", {
        "request": request, "user": user, "submissions": subs, "unread_count": unread, "now": datetime.now()
    })

# 3. 任务详情
@router.get("/task/{task_id}")
def h5_task_detail(task_id: int, request: Request, user = Depends(deps.get_current_active_user), db: Session = Depends(get_db)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task: return RedirectResponse("/h5/index")
    
    sub = db.query(models.Submission).filter(models.Submission.user_id == user.id, models.Submission.task_id == task_id).first()
    mat = None
    if sub and sub.assigned_material_id:
        mat = db.query(models.Material).filter(models.Material.id == sub.assigned_material_id).first()
        
    return templates.TemplateResponse("h5/detail.html", {
        "request": request, "user": user, "task": task, "existing_sub": sub, "assigned_material": mat
    })

# 4. 抢单接口
@router.post("/task/{task_id}/grab")
def h5_task_grab(task_id: int, user = Depends(deps.get_current_active_user), db: Session = Depends(get_db)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    
    mat_id = None
    if task.material_category_id:
        mat = db.query(models.Material).filter(
            models.Material.category_id == task.material_category_id,
            models.Material.status == "unused"
        ).first()
        if not mat: return RedirectResponse(f"/h5/task/{task_id}?msg=NoMaterial", status_code=302)
        mat.status = "locked"
        mat.used_by_user_id = user.id
        mat_id = mat.id
        
    db.add(models.Submission(user_id=user.id, task_id=task_id, status="pending_upload", assigned_material_id=mat_id))
    db.commit()
    return RedirectResponse(f"/h5/task/{task_id}", status_code=302)

# 5. 排行榜
@router.get("/rank")
def h5_rank(request: Request, user = Depends(deps.get_current_active_user), db: Session = Depends(get_db)):
    rich = db.query(models.User).order_by(models.User.balance.desc()).limit(20).all()
    return templates.TemplateResponse("h5/rank.html", {"request": request, "user": user, "rich_list": rich, "diligence_list": []})

# 6. 充值页
@router.get("/recharge")
def h5_recharge(request: Request, user = Depends(deps.get_current_active_user), db: Session = Depends(get_db)):
    code = db.query(models.SystemConfig).filter(models.SystemConfig.key == "pay_qrcode").first()
    return templates.TemplateResponse("h5/recharge.html", {"request": request, "user": user, "pay_qrcode": code.value if code else None})

# 7. 充值提交
@router.post("/recharge/submit")
def h5_recharge_sub(amount: float = Form(...), user = Depends(deps.get_current_active_user), db: Session = Depends(get_db)):
    # 简化逻辑，实际应处理文件上传
    db.add(models.Deposit(user_id=user.id, amount=amount, status="pending"))
    db.commit()
    return RedirectResponse("/h5/mine", status_code=302)

# 8. 提现页
@router.get("/withdraw")
def h5_withdraw(request: Request, user = Depends(deps.get_current_active_user)):
    return templates.TemplateResponse("h5/withdraw.html", {"request": request, "user": user})

# 9. 提现提交
@router.post("/withdraw/submit")
def h5_withdraw_sub(amount: float = Form(...), real_name: str = Form(...), account: str = Form(...), user = Depends(deps.get_current_active_user), db: Session = Depends(get_db)):
    if user.balance < amount: return "余额不足"
    user.balance -= amount
    db.add(models.Withdrawal(user_id=user.id, amount=amount, real_name=real_name, account=account))
    db.commit()
    return RedirectResponse("/h5/mine", status_code=302)

# 10. 邀请页
@router.get("/invite")
def h5_invite(request: Request, user = Depends(deps.get_current_active_user), db: Session = Depends(get_db)):
    children = db.query(models.User).filter(models.User.inviter_id == user.id).all()
    return templates.TemplateResponse("h5/invite.html", {"request": request, "user": user, "children": children, "base_url": str(request.base_url).rstrip("/")})

# 11. 消息中心
@router.get("/messages")
def h5_messages(request: Request, user = Depends(deps.get_current_active_user), db: Session = Depends(get_db)):
    notes = db.query(models.Notification).filter(models.Notification.user_id == user.id).all()
    return templates.TemplateResponse("h5/messages.html", {"request": request, "user": user, "notifications": notes})

# 12. 设置页
@router.get("/settings")
def h5_settings(request: Request, user = Depends(deps.get_current_active_user)):
    return templates.TemplateResponse("h5/settings.html", {"request": request, "user": user})

# 13. VIP页
@router.get("/vip")
def h5_vip(request: Request, user = Depends(deps.get_current_active_user), db: Session = Depends(get_db)):
    plans = db.query(models.VipPlan).all()
    return templates.TemplateResponse("h5/vip.html", {"request": request, "user": user, "plans": plans, "is_vip": False})