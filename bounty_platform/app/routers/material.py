from fastapi import APIRouter, Depends, UploadFile, File, Form, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import json
from ..database import get_db
from .. import models
from ..core import deps
from ..services.risk_control import save_upload_file_sync

router = APIRouter(prefix="/admin/materials", tags=["CMS"])
templates = Jinja2Templates(directory="app/templates")

@router.get("", include_in_schema=False)
def view_materials_page(request: Request, db: Session = Depends(get_db), user=Depends(deps.get_current_admin)):
    cats = db.query(models.MaterialCategory).order_by(models.MaterialCategory.created_at.desc()).all()
    return templates.TemplateResponse("admin/materials.html", {"request": request, "user": user, "categories": cats})

@router.get("/list/{cat_id}")
def list_materials_api(cat_id: int, db: Session = Depends(get_db)):
    mats = db.query(models.Material).filter(models.Material.category_id == cat_id, models.Material.is_deleted == False).order_by(models.Material.id.desc()).all()
    return [{"id": m.id, "title": m.title, "content": m.content, "images": json.loads(m.images) if m.images else [], "status": m.status} for m in mats]

@router.post("/upload")
def upload_material(cat_id: int = Form(...), files: List[UploadFile] = File(...), is_carousel: bool = Form(False), title: str = Form(...), content: str = Form(...), db: Session = Depends(get_db)):
    paths = [save_upload_file_sync(f) for f in files if f.filename]
    if not paths: return {"code": 400, "message": "未选择文件"}
    
    count = 0
    if is_carousel:
        db.add(models.Material(category_id=cat_id, title=title, content=content, images=json.dumps(paths), status="unused")); count = 1
    else:
        for p in paths: db.add(models.Material(category_id=cat_id, title=title, content=content, images=json.dumps([p]), status="unused")); count += 1
            
    cat = db.query(models.MaterialCategory).filter(models.MaterialCategory.id == cat_id).first()
    if cat: cat.total_count += count
    db.commit()
    return {"code": 200, "message": "上传成功"}

@router.post("/recycle")
def recycle_material(mat_id: int = Form(...), db: Session = Depends(get_db)):
    mat = db.query(models.Material).filter(models.Material.id == mat_id).first()
    if mat:
        mat.is_deleted = True
        db.commit()
    return {"code": 200, "message": "已删除"}

@router.post("/category/new")
def new_cat(name: str = Form(...), db: Session = Depends(get_db)):
    db.add(models.MaterialCategory(name=name))
    db.commit()
    return {"code": 200, "message": "创建成功"}