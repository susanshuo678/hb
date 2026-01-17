from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime
from ..database import get_db
from .. import models
from ..core import deps

router = APIRouter(prefix="/user", tags=["User"])

@router.post("/checkin")
def checkin(user: models.User = Depends(deps.get_current_active_user), db: Session = Depends(get_db)):
    today = datetime.now().strftime("%Y-%m-%d")
    if db.query(models.CheckIn).filter(models.CheckIn.user_id == user.id, models.CheckIn.date == today).first():
        return {"code": 400, "message": "今日已签到"}
        
    db.add(models.CheckIn(user_id=user.id, date=today))
    user.balance += 0.5
    db.add(models.Notification(user_id=user.id, title="签到奖励", content="获得 0.5 元"))
    db.commit()
    return {"code": 200, "message": "签到成功 +0.5元"}