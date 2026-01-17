from fastapi import APIRouter, Depends, UploadFile, File, Form, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import List
import json
from ..database import get_db
from .. import models
from ..core import deps
from ..services.risk_control import save_upload_file_sync

# 注意：这里 prefix 是 /admin/materials
router = APIRouter(prefix="/admin/materials", tags=["Material"])
templates = Jinja2Templates(directory="app/templates")

# 🟢 1. 素材库页面 (解决 404 的关键)
@router.get("", include_in_schema=False)
def view_materials_page(
    request: Request, 
    db: Session = Depends(get_db),
    user=Depends(deps.get_current_admin)
):
    cats = db.query(models.MaterialCategory).order_by(models.MaterialCategory.created_at.desc()).all()
    return templates.TemplateResponse("admin/materials.html", {
        "request": request, 
        "user": user, 
        "categories": cats
    })

# 🟢 2. 获取素材列表 API
@router.get("/list/{cat_id}")
def list_materials_api(cat_id: int, db: Session = Depends(get_db)):
    mats = db.query(models.Material).filter(
        models.Material.category_id == cat_id,
        models.Material.is_deleted == False
    ).order_by(models.Material.id.desc()).all()
    
    return [
        {
            "id": m.id,
            "title": m.title,
            "content": m.content,
            "images": json.loads(m.images) if m.images else [],
            "status": m.status
        } 
        for m in mats
    ]

# 🟢 3. 上传接口
@router.post("/upload")
def upload_material(
    cat_id: int = Form(...),
    files: List[UploadFile] = File(...),
    is_carousel: bool = Form(False),
    title: str = Form(...),
    content: str = Form(...),
    db: Session = Depends(get_db)
):
    paths = []
    for file in files:
        if file.filename:
            paths.append(save_upload_file_sync(file))
            
    if not paths: return {"code": 400, "message": "未选择文件"}

    count = 0
    if is_carousel:
        # 合并模式
        db.add(models.Material(
            category_id=cat_id, title=title, content=content,
            images=json.dumps(paths), status="unused"
        ))
        count = 1
    else:
        # 拆分模式
        for p in paths:
            db.add(models.Material(
                category_id=cat_id, title=title, content=content,
                images=json.dumps([p]), status="unused"
            ))
            count += 1
            
    # 更新分类计数
    cat = db.query(models.MaterialCategory).filter(models.MaterialCategory.id == cat_id).first()
    if cat: cat.total_count += count
    db.commit()
    
    return {"code": 200, "message": "上传成功", "data": {"count": count}}

# 🟢 4. 编辑素材接口 (新增需求)
@router.post("/update")
def update_material(
    mat_id: int = Form(...),
    title: str = Form(...),
    content: str = Form(...),
    db: Session = Depends(get_db)
):
    mat = db.query(models.Material).filter(models.Material.id == mat_id).first()
    if not mat: return {"code": 404, "message": "素材不存在"}
    
    mat.title = title
    mat.content = content
    db.commit()
    return {"code": 200, "message": "修改成功"}

# 🟢 5. 移入回收站
@router.post("/recycle")
def recycle_material(mat_id: int = Form(...), db: Session = Depends(get_db)):
    mat = db.query(models.Material).filter(models.Material.id == mat_id).first()
    if mat:
        mat.is_deleted = True
        
        # 减少计数
        cat = db.query(models.MaterialCategory).filter(models.MaterialCategory.id == mat.category_id).first()
        if cat and cat.total_count > 0: cat.total_count -= 1
        
        db.commit()
    return {"code": 200, "message": "已移入回收站"}

# 🟢 6. 新建分类
@router.post("/category/new")
def new_category(name: str = Form(...), db: Session = Depends(get_db)):
    db.add(models.MaterialCategory(name=name))
    db.commit()
    return {"code": 200, "message": "创建成功"} # 注意：前端使用的是Redirect还是Ajax? V3建议统一Ajax
    # 如果前端是 form submit 跳转，这里需要改回 RedirectResponse。
    # 为了兼容你现在的前端，我们让前端改用 Ajax 吧 (base.html 里的 apiPost)