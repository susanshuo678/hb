from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi_limiter import FastAPILimiter
from .database import engine, Base, redis_conn
# 引入所有 Router
from .routers import auth, user, admin, material, common, h5

Base.metadata.create_all(bind=engine)

app = FastAPI(title="红白悬赏 V3 Enterprise")
app.mount("/static", StaticFiles(directory="/app/app/static"), name="static")

# 注册所有模块
app.include_router(auth.router)
app.include_router(user.router) # 用户API
app.include_router(h5.router)   # 🟢 H5页面路由 (新增)
app.include_router(admin.router)
app.include_router(material.router)
app.include_router(common.router)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"code": 500, "message": f"Server Error: {str(exc)}"})

@app.on_event("startup")
async def startup():
    await FastAPILimiter.init(redis_conn)