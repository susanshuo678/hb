import hashlib
import os
import shutil
import uuid
from fastapi import UploadFile
from sqlalchemy.orm import Session

class RiskControlService:
    @staticmethod
    def calculate_file_md5(file_path: str) -> str:
        hash_md5 = hashlib.md5()
        if not os.path.exists(file_path): return ""
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    @staticmethod
    def is_duplicate_image(db: Session, md5_hash: str) -> bool:
        from app.models import Submission
        exists = db.query(Submission).filter(
            Submission.image_hash == md5_hash,
            Submission.status != "rejected" 
        ).first()
        return exists is not None

# 辅助函数：同步保存文件
def save_upload_file_sync(file: UploadFile, folder: str = "app/static/uploads") -> str:
    os.makedirs(folder, exist_ok=True)
    filename = file.filename or f"{uuid.uuid4()}.jpg"
    file_path = os.path.join(folder, filename)
    
    # 避免文件名冲突
    if os.path.exists(file_path):
        filename = f"{uuid.uuid4()}_{filename}"
        file_path = os.path.join(folder, filename)
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        print(f"❌ Upload Failed: {e}")
        return ""
        
    # 返回相对路径 (去除 app 前缀，前端直接用 /static/...)
    return file_path.replace("app", "", 1)