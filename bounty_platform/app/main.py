import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi_limiter import FastAPILimiter
from starlette.middleware.sessions import SessionMiddleware

from .database import engine, Base, redis_conn
from .core.config import settings
from .core.logger import logger  # 🟢 引入日志
from .routers import auth, user, admin, material, h5, common

# 1. 确保上传目录存在
os.makedirs("app/static/uploads", exist_ok=True)

# 2. 自动建表
Base.metadata.create_all(bind=engine)

# 3. 初始化 APP
app = FastAPI(title="红白悬赏 V3 Enterprise")

# 4. 中间件
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)

# 5. 静态资源挂载
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# 6. 注册路由
app.include_router(auth.router)
app.include_router(user.router)
app.include_router(admin.router)
app.include_router(material.router)
app.include_router(h5.router)
app.include_router(common.router)

# 7. 全局异常处理 (🟢 记录到日志文件)
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"System Error: {exc}", exc_info=True) # 记录堆栈
    return JSONResponse(status_code=500, content={"code": 500, "message": f"系统错误: {str(exc)}"})

@app.get("/")
async def root():
    return RedirectResponse(url="/h5/index")

# 8. 启动事件
@app.on_event("startup")
async def startup():
    try:
        await redis_conn.ping()
        await FastAPILimiter.init(redis_conn)
        logger.info("✅ Redis Connected & Limiter Initialized")
    except Exception as e:
        logger.error(f"❌ Redis Connection Failed: {e}")