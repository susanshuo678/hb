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

@router.get("/index")
def h5_index(request: Request, cat: str = "all", user = Depends(deps.get_current_active_user), db: Session = Depends(get_db)):
    tasks = db.query(models.Task).filter(models.Task.is_active == True).order_by(models.Task.id.desc()).all()
    return templates.TemplateResponse("h5/index.html", {"request": request, "user": user, "tasks": tasks, "banners": [], "categories": [], "announcement": "", "current_cat": cat})

@router.get("/mine")
def h5_mine(request: Request, user = Depends(deps.get_current_active_user), db: Session = Depends(get_db)):
    subs = db.query(models.Submission).filter(models.Submission.user_id == user.id).all()
    return templates.TemplateResponse("h5/mine.html", {"request": request, "user": user, "submissions": subs, "unread_count": 0, "now": datetime.now()})

@router.get("/task/{task_id}")
def h5_task_detail(task_id: int, request: Request, user = Depends(deps.get_current_active_user), db: Session = Depends(get_db)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    sub = db.query(models.Submission).filter(models.Submission.user_id == user.id, models.Submission.task_id == task_id).first()
    mat = db.query(models.Material).filter(models.Material.id == sub.assigned_material_id).first() if (sub and sub.assigned_material_id) else None
    return templates.TemplateResponse("h5/detail.html", {"request": request, "user": user, "task": task, "existing_sub": sub, "assigned_material": mat})

@router.post("/task/{task_id}/grab")
def h5_grab(task_id: int, user = Depends(deps.get_current_active_user), db: Session = Depends(get_db)):
    db.add(models.Submission(user_id=user.id, task_id=task_id, status="pending_upload"))
    db.commit()
    return RedirectResponse(f"/h5/task/{task_id}", status_code=302)