import shutil
import uuid
import os
from fastapi import UploadFile

# 确保上传目录存在
UPLOAD_DIR = "app/static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def save_upload_file_sync(file: UploadFile) -> str:
    """
    同步保存文件，防止 async 卡死主线程
    """
    try:
        # 提取扩展名
        filename = file.filename
        ext = filename.split(".")[-1] if "." in filename else "jpg"
        
        # 生成唯一文件名
        unique_name = f"{uuid.uuid4()}.{ext}"
        file_path = os.path.join(UPLOAD_DIR, unique_name)
        
        # 写入磁盘
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # 返回用于前端访问的 URL 路径 (注意：这里返回的是相对路径，配合 Nginx 或 StaticFiles 使用)
        return f"/static/uploads/{unique_name}"
        
    except Exception as e:
        print(f"Error saving file: {e}")
        return ""