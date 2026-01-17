from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi_limiter import FastAPILimiter
# 导入配置和路由
from .database import engine, Base, redis_conn
from .routers import auth, user, admin, material, common, h5

# 1. 自动建表
Base.metadata.create_all(bind=engine)

# 2. 初始化 APP
app = FastAPI(title="红白悬赏 V3 Enterprise")

# 3. 挂载静态文件 (图片)
app.mount("/static", StaticFiles(directory="/app/app/static"), name="static")

# 4. 注册所有业务路由 (把分散的功能装回来)
app.include_router(auth.router)
app.include_router(user.router)
app.include_router(admin.router)    # 管理后台
app.include_router(material.router) # 素材库 (之前缺这个)
app.include_router(h5.router)       # H5前台 (之前缺这个)
app.include_router(common.router)

# 5. 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"code": 500, "message": f"系统错误: {str(exc)}"}
    )

# 6. 启动事件
@app.on_event("startup")
async def startup():
    await FastAPILimiter.init(redis_conn)