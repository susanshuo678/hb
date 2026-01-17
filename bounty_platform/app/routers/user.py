from fastapi import APIRouter, Depends, Form
from sqlalchemy.orm import Session
from datetime import datetime
from ..database import get_db
from .. import models
from ..core import deps

router = APIRouter(prefix="/user", tags=["User"])

# 1. 每日签到
@router.post("/checkin")
def daily_checkin(
    user: models.User = Depends(deps.get_current_active_user),
    db: Session = Depends(get_db)
):
    today = datetime.now().strftime("%Y-%m-%d")
    exists = db.query(models.CheckIn).filter(
        models.CheckIn.user_id == user.id, 
        models.CheckIn.date == today
    ).first()
    
    if exists:
        return {"code": 400, "message": "今日已签到"}
        
    # 签到逻辑
    db.add(models.CheckIn(user_id=user.id, date=today))
    reward = 0.5 # 每日奖励
    user.balance += reward
    
    # 记录日志
    log = models.Notification(user_id=user.id, title="签到奖励", content=f"获得 {reward} 元")
    db.add(log)
    db.commit()
    
    return {"code": 200, "message": f"签到成功，获得 {reward} 元"}

# 2. 订单申诉
@router.post("/appeal")
def submit_appeal(
    sub_id: int = Form(...),
    reason: str = Form(...),
    user: models.User = Depends(deps.get_current_active_user),
    db: Session = Depends(get_db)
):
    sub = db.query(models.Submission).filter(models.Submission.id == sub_id, models.Submission.user_id == user.id).first()
    if not sub or sub.status != "rejected":
        return {"code": 400, "message": "该订单无法申诉"}
        
    sub.status = "appealing" # 变更为申诉中
    sub.appeal_reason = reason
    db.commit()
    return {"code": 200, "message": "申诉已提交，请等待管理员复审"}