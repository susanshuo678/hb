from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import json

from app.database import get_db
from app.models import Material, MaterialCategory, User
from app.core import deps
from app.services.risk_control import save_upload_file_sync

router = APIRouter(prefix="/admin/materials", tags=["Material"])

# 1. 素材列表 (🟢 新增 keyword 搜索)
@router.get("/list/{cat_id}")
async def list_materials(
    cat_id: int, 
    keyword: str = Query(None), # 🟢 支持搜索
    db: Session = Depends(get_db), 
    current_user: User = Depends(deps.get_current_admin)
):
    query = db.query(Material).filter(Material.is_deleted == False)
    
    if cat_id > 0:
        query = query.filter(Material.category_id == cat_id)
        
    if keyword:
        query = query.filter(Material.title.contains(keyword))
        
    mats = query.order_by(Material.created_at.desc()).all()
    
    res = []
    for m in mats:
        # 解析 JSON 图片列表
        imgs = m.images
        if isinstance(imgs, str):
            try:
                imgs = json.loads(imgs)
            except:
                imgs = [imgs]
                
        res.append({
            "id": m.id,
            "title": m.title,
            "content": m.content,
            "images": imgs, 
            "created_at": m.created_at.strftime("%Y-%m-%d") if m.created_at else ""
        })
    return res

# 2. 上传素材 (保持不变)
@router.post("/upload")
async def upload_material(
    cat_id: int = Form(...),
    title: str = Form(...),
    content: str = Form(""),
    is_carousel: bool = Form(False),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_admin)
):
    image_paths = []
    for file in files:
        path = save_upload_file_sync(file)
        if path: image_paths.append(path)
            
    if not image_paths: return {"code": 400, "message": "未上传图片"}

    # 获取分类用于统计
    cat = db.query(MaterialCategory).filter(MaterialCategory.id == cat_id).first()

    if is_carousel:
        # 多图合一
        new_mat = Material(category_id=cat_id, title=title, content=content, images=image_paths, status="unused")
        db.add(new_mat)
        if cat: cat.total_count += 1
    else:
        # 拆分上传
        for img_path in image_paths:
            new_mat = Material(category_id=cat_id, title=title, content=content, images=[img_path], status="unused")
            db.add(new_mat)
        if cat: cat.total_count += len(image_paths)

    db.commit()
    return {"code": 200, "message": "上传成功"}

# 3. 🟢 新增：批量操作 (删除/移动)
@router.post("/batch")
async def batch_operate_materials(
    action: str = Form(...), # 'delete' or 'move'
    material_ids: str = Form(...), # JSON 字符串: "[1, 2, 3]"
    target_cat_id: int = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_admin)
):
    try:
        ids = json.loads(material_ids)
    except:
        return {"code": 400, "message": "参数错误"}
        
    if not ids: return {"code": 400, "message": "未选择素材"}

    mats = db.query(Material).filter(Material.id.in_(ids)).all()
    
    if action == "delete":
        for m in mats:
            m.is_deleted = True
            # 减少计数
            cat = db.query(MaterialCategory).filter(MaterialCategory.id == m.category_id).first()
            if cat and cat.total_count > 0: cat.total_count -= 1
    
    elif action == "move":
        if not target_cat_id: return {"code": 400, "message": "请选择目标分类"}
        target_cat = db.query(MaterialCategory).filter(MaterialCategory.id == target_cat_id).first()
        if not target_cat: return {"code": 404, "message": "目标分类不存在"}
        
        for m in mats:
            # 减少旧分类计数
            old_cat = db.query(MaterialCategory).filter(MaterialCategory.id == m.category_id).first()
            if old_cat and old_cat.total_count > 0: old_cat.total_count -= 1
            
            # 移动
            m.category_id = target_cat_id
            
            # 增加新分类计数
            target_cat.total_count += 1

    db.commit()
    return {"code": 200, "message": f"成功操作 {len(ids)} 条素材"}

# 4. 分类管理 (保持不变)
@router.post("/category/add")
async def add_material_category(name: str = Form(...), db: Session = Depends(get_db), current_user: User = Depends(deps.get_current_admin)):
    if db.query(MaterialCategory).filter(MaterialCategory.name == name).first():
        return {"code": 400, "message": "分类名称已存在"}
    new_cat = MaterialCategory(name=name, total_count=0, used_count=0)
    db.add(new_cat)
    db.commit()
    return {"code": 200, "message": "分类创建成功"}

@router.post("/category/delete")
async def delete_material_category(cat_id: int = Form(...), db: Session = Depends(get_db), current_user: User = Depends(deps.get_current_admin)):
    cat = db.query(MaterialCategory).filter(MaterialCategory.id == cat_id).first()
    if cat:
        db.delete(cat)
        db.commit()
    return {"code": 200, "message": "删除成功"}