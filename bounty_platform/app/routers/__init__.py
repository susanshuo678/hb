from .auth import router as auth_router
from .user import router as user_router
from .admin import router as admin_router
from .material import router as material_router
from .common import router as common_router

# 方便 main.py 导入
__all__ = ["auth_router", "user_router", "admin_router", "material_router", "common_router"]