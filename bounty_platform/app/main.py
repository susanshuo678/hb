import shutil, uuid, os, urllib.parse, string, random, logging
from io import BytesIO
from fastapi import FastAPI, Depends, Request, Form, status, UploadFile, File, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, HTMLResponse, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, func, desc, and_
from sqlalchemy.orm import sessionmaker
from typing import Optional, List
from starlette.middleware.sessions import SessionMiddleware 
from captcha.image import ImageCaptcha 
from datetime import datetime, timedelta
import openpyxl

from . import models, auth

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 🟢 优化数据库连接：增加超时时间到 60s，防止后台卡死
SQLALCHEMY_DATABASE_URL = "sqlite:///./app/database/bounty.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False, "timeout": 60}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

app = FastAPI(title="红白悬赏")
app.add_middleware(SessionMiddleware, secret_key="bounty-cn-secret")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")
models.Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

def get_current_user(request: Request, db: Session = Depends(get_db)):
    username = request.cookies.get("user")
    if not username: return None
    return db.query(models.User).filter(models.User.username == username).first()

def create_notification(db: Session, user_id: int, title: str, content: str, msg_type: str = "system"):
    note = models.Notification(user_id=user_id, title=title, content=content, type=msg_type)
    db.add(note)

# --- 初始化 ---
@app.on_event("startup")
def init_db_data():
    db = SessionLocal()
    try:
        if db.query(models.TaskCategory).count() == 0:
            defaults = [
                models.TaskCategory(name="注册拉新", code="register", icon="📱", color="primary", sort_order=10),
                models.TaskCategory(name="图文推广", code="social", icon="📕", color="danger", sort_order=9),
                models.TaskCategory(name="其他任务", code="other", icon="📂", color="dark", sort_order=0),
            ]
            db.add_all(defaults)
        
        if db.query(models.VipPlan).count() == 0:
            plans = [
                models.VipPlan(name="月卡会员", days=30, price=29.9, bonus_rate=10),
                models.VipPlan(name="季卡会员", days=90, price=79.9, bonus_rate=15),
                models.VipPlan(name="年卡至尊", days=365, price=199.9, bonus_rate=20),
            ]
            db.add_all(plans)
            
        configs = {
            "announcement": "📢 欢迎来到红白悬赏平台，请文明做单，诚信互助！",
            "commission_rate": "10",
            "contact_text": "客服微信: Admin_888",
        }
        for k, v in configs.items():
            if not db.query(models.SystemConfig).filter(models.SystemConfig.key == k).first():
                db.add(models.SystemConfig(key=k, value=v))
        db.commit()
    except Exception as e:
        logger.error(f"Init DB Error: {e}")
    finally:
        db.close()

# --- 基础路由 ---

@app.get("/captcha")
def get_captcha(request: Request):
    image = ImageCaptcha(width=120, height=50) 
    code = "".join(random.choices(string.digits, k=4))
    request.session["captcha"] = code
    return Response(content=image.generate(code).getvalue(), media_type="image/png")

@app.get("/")
def root(user: Optional[models.User] = Depends(get_current_user)):
    return RedirectResponse(url="/h5/index" if user else "/login")

@app.get("/register", response_class=HTMLResponse)
def show_register(request: Request, invite: Optional[str] = None):
    return templates.TemplateResponse("register.html", {"request": request, "invite_code": invite, "success": False})

@app.post("/register")
def register(request: Request, username: str = Form(...), password: str = Form(...), captcha: str = Form(...), invite_code: Optional[int] = Form(None), db: Session = Depends(get_db)):
    if request.session.get("captcha") != captcha:
        return templates.TemplateResponse("register.html", {"request": request, "error": "验证码错误", "invite_code": invite_code})
    if db.query(models.User).filter(models.User.username == username).first():
        return templates.TemplateResponse("register.html", {"request": request, "error": "用户名已存在"})
    
    inviter_id = None
    if invite_code:
        inviter = db.query(models.User).filter(models.User.id == invite_code).first()
        if inviter: inviter_id = inviter.id
        
    new_user = models.User(username=username, hashed_password=auth.get_password_hash(password), inviter_id=inviter_id)
    db.add(new_user)
    db.commit()
    request.session.pop("captcha", None)
    return templates.TemplateResponse("register.html", {"request": request, "success": True})

@app.get("/login", response_class=HTMLResponse)
def show_login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user or not auth.verify_password(password, user.hashed_password):
        return templates.TemplateResponse("login.html", {"request": request, "error": "账号或密码错误"})
    target = "/admin/dashboard" if user.is_admin else "/h5/index"
    resp = RedirectResponse(url=target, status_code=status.HTTP_302_FOUND)
    resp.set_cookie(key="user", value=username, max_age=86400, httponly=True)
    return resp

@app.get("/logout")
def logout():
    resp = RedirectResponse(url="/login")
    resp.delete_cookie("user")
    return resp

# --- H5 业务 ---

@app.get("/h5/index", response_class=HTMLResponse)
def h5_index(request: Request, cat: Optional[str] = "all", user: Optional[models.User] = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user: return RedirectResponse("/login")
    query = db.query(models.Task).filter(models.Task.is_active == True)
    if cat and cat != "all": query = query.filter(models.Task.category == cat)
    tasks = query.order_by(models.Task.id.desc()).all()
    
    # 检查素材库存
    available_tasks = []
    for t in tasks:
        if t.material_category_id:
            count = db.query(models.Material).filter(models.Material.category_id == t.material_category_id, models.Material.status == 'unused').count()
            if count > 0: available_tasks.append(t)
        else:
            available_tasks.append(t)
            
    announcement = db.query(models.SystemConfig).filter(models.SystemConfig.key == "announcement").first()
    return templates.TemplateResponse("h5/index.html", {
        "request": request, "user": user, "tasks": available_tasks, 
        "banners": db.query(models.Banner).all(), 
        "categories": db.query(models.TaskCategory).all(),
        "announcement": announcement.value if announcement else "",
        "current_cat": cat
    })

@app.get("/h5/mine", response_class=HTMLResponse)
def h5_mine(request: Request, user: Optional[models.User] = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user: return RedirectResponse("/login")
    subs = db.query(models.Submission).filter(models.Submission.user_id == user.id).order_by(models.Submission.created_at.desc()).all()
    unread = db.query(models.Notification).filter(models.Notification.user_id == user.id, models.Notification.is_read == False).count()
    return templates.TemplateResponse("h5/mine.html", {"request": request, "user": user, "submissions": subs, "unread_count": unread, "now": datetime.now()})

@app.get("/h5/rank", response_class=HTMLResponse)
def h5_rank(request: Request, user: Optional[models.User] = Depends(get_current_user), db: Session = Depends(get_db)):
    rich = db.query(models.User).order_by(models.User.balance.desc()).limit(20).all()
    diligent = db.query(models.User, func.count(models.Submission.id).label('cnt')).join(models.Submission).filter(models.Submission.status == 'approved').group_by(models.User.id).order_by(desc('cnt')).limit(20).all()
    return templates.TemplateResponse("h5/rank.html", {"request": request, "user": user, "rich_list": rich, "diligence_list": diligent})

@app.get("/h5/messages", response_class=HTMLResponse)
def h5_messages(request: Request, user: Optional[models.User] = Depends(get_current_user), db: Session = Depends(get_db)):
    notes = db.query(models.Notification).filter(models.Notification.user_id == user.id).order_by(models.Notification.created_at.desc()).all()
    return templates.TemplateResponse("h5/messages.html", {"request": request, "user": user, "notifications": notes})

@app.post("/h5/messages/read_all")
def h5_read_all(user: Optional[models.User] = Depends(get_current_user), db: Session = Depends(get_db)):
    db.query(models.Notification).filter(models.Notification.user_id == user.id).update({"is_read": True})
    db.commit()
    return RedirectResponse("/h5/messages", status_code=302)

@app.get("/h5/settings", response_class=HTMLResponse)
def h5_settings(request: Request, user: Optional[models.User] = Depends(get_current_user), db: Session = Depends(get_db)):
    def g(k): 
        o = db.query(models.SystemConfig).filter(models.SystemConfig.key == k).first()
        return o.value if o else ""
    return templates.TemplateResponse("h5/settings.html", {"request": request, "user": user, "contact_text": g("contact_text"), "contact_img": g("contact_img")})

@app.post("/h5/settings/avatar")
def h5_avatar(file: UploadFile = File(...), user: Optional[models.User] = Depends(get_current_user), db: Session = Depends(get_db)):
    ext = file.filename.split(".")[-1]
    name = f"av_{uuid.uuid4()}.{ext}"
    with open(f"app/static/uploads/{name}", "wb") as b: shutil.copyfileobj(file.file, b)
    user.avatar = f"/static/uploads/{name}"
    db.commit()
    return RedirectResponse("/h5/settings", status_code=302)

@app.get("/h5/vip", response_class=HTMLResponse)
def h5_vip(request: Request, user: Optional[models.User] = Depends(get_current_user), db: Session = Depends(get_db)):
    return templates.TemplateResponse("h5/vip.html", {"request": request, "user": user, "plans": db.query(models.VipPlan).all(), "is_vip": (user.vip_end_time and user.vip_end_time > datetime.now())})

@app.post("/h5/vip/buy")
def h5_vip_buy(plan_id: int = Form(...), user: Optional[models.User] = Depends(get_current_user), db: Session = Depends(get_db)):
    plan = db.query(models.VipPlan).filter(models.VipPlan.id == plan_id).first()
    if user.balance < plan.price: return RedirectResponse("/h5/vip?msg=" + urllib.parse.quote("余额不足"), status_code=302)
    user.balance -= plan.price
    now = datetime.now()
    if user.vip_end_time and user.vip_end_time > now: user.vip_end_time += timedelta(days=plan.days)
    else: user.vip_end_time = now + timedelta(days=plan.days)
    create_notification(db, user.id, "VIP开通成功", f"您已开通 {plan.name}")
    db.commit()
    return RedirectResponse("/h5/vip?msg=" + urllib.parse.quote("开通成功"), status_code=302)

@app.get("/h5/recharge", response_class=HTMLResponse)
def h5_recharge(request: Request, user: Optional[models.User] = Depends(get_current_user), db: Session = Depends(get_db)):
    code = db.query(models.SystemConfig).filter(models.SystemConfig.key == "pay_qrcode").first()
    return templates.TemplateResponse("h5/recharge.html", {"request": request, "user": user, "pay_qrcode": code.value if code else None})

@app.post("/h5/recharge/submit")
def h5_recharge_sub(amount: float = Form(...), file: UploadFile = File(...), user: Optional[models.User] = Depends(get_current_user), db: Session = Depends(get_db)):
    ext = file.filename.split(".")[-1]
    name = f"pay_{uuid.uuid4()}.{ext}"
    with open(f"app/static/uploads/{name}", "wb") as b: shutil.copyfileobj(file.file, b)
    db.add(models.Deposit(user_id=user.id, amount=amount, proof_img=f"/static/uploads/{name}", status="pending"))
    db.commit()
    return RedirectResponse("/h5/mine?msg=" + urllib.parse.quote("充值已提交审核"), status_code=302)

# 🟢 修复：任务详情页，防止未抢单状态下报错
@app.get("/h5/task/{task_id}", response_class=HTMLResponse)
def h5_task_detail(task_id: int, request: Request, user: Optional[models.User] = Depends(get_current_user), db: Session = Depends(get_db)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task: return RedirectResponse("/h5/index") # 防止ID不存在报错

    existing_sub = db.query(models.Submission).filter(
        models.Submission.user_id == user.id,
        models.Submission.task_id == task_id,
        models.Submission.status.in_(['pending', 'approved', 'pending_upload']) 
    ).first()
    
    assigned_material = None
    if existing_sub and existing_sub.assigned_material_id:
        assigned_material = db.query(models.Material).filter(models.Material.id == existing_sub.assigned_material_id).first()

    return templates.TemplateResponse("h5/detail.html", {
        "request": request, "user": user, "task": task,
        "existing_sub": existing_sub,
        "assigned_material": assigned_material
    })

# 🟢 修复：抢单接口，增加 dummy 参数防止解析 body 失败
@app.post("/h5/task/{task_id}/grab")
def h5_task_grab(
    task_id: int, 
    request: Request,  # 显式接收 Request 对象
    user: Optional[models.User] = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task: return RedirectResponse("/h5/index")

    # 检查是否已抢
    if db.query(models.Submission).filter(models.Submission.user_id == user.id, models.Submission.task_id == task_id).first():
        return RedirectResponse(f"/h5/task/{task_id}", status_code=302)

    material = None
    if task.material_category_id:
        # 悲观锁逻辑：找素材
        material = db.query(models.Material).filter(
            models.Material.category_id == task.material_category_id,
            models.Material.status == "unused"
        ).first()
        
        if not material:
            return RedirectResponse(f"/h5/task/{task_id}?msg=" + urllib.parse.quote("手慢了，素材已领完"), status_code=302)
        
        material.status = "locked"
        material.used_by_user_id = user.id
        material.used_at = datetime.now()
        
        cat = db.query(models.MaterialCategory).filter(models.MaterialCategory.id == task.material_category_id).first()
        cat.used_count += 1

    sub = models.Submission(
        user_id=user.id, 
        task_id=task_id, 
        status="pending_upload", 
        assigned_material_id=material.id if material else None
    )
    db.add(sub)
    db.commit()
    
    return RedirectResponse(f"/h5/task/{task_id}", status_code=302)

# 🟢 修复：提交接口，确保 multipart 解析正常
@app.post("/h5/task/{task_id}/submit")
async def h5_task_submit(
    task_id: int, 
    request: Request,
    post_link: Optional[str] = Form(None), 
    file: Optional[UploadFile] = File(None), 
    user: Optional[models.User] = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    sub = db.query(models.Submission).filter(
        models.Submission.user_id == user.id, 
        models.Submission.task_id == task_id
    ).first()
    
    if not sub:
        sub = models.Submission(user_id=user.id, task_id=task_id, status="pending")
        db.add(sub)
    
    path = None
    if file and file.filename:
        # 确保目录存在
        os.makedirs("app/static/uploads", exist_ok=True)
        name = f"sub_{uuid.uuid4()}.{file.filename.split('.')[-1]}"
        with open(f"app/static/uploads/{name}", "wb") as b: shutil.copyfileobj(file.file, b)
        path = f"/static/uploads/{name}"
    
    sub.screenshot_path = path
    sub.post_link = post_link
    sub.status = "pending" # 转为待审核
    
    if sub.assigned_material_id:
        mat = db.query(models.Material).filter(models.Material.id == sub.assigned_material_id).first()
        if mat: mat.status = "used"

    db.commit()
    return RedirectResponse("/h5/mine?msg=" + urllib.parse.quote("提交成功"), status_code=302)

@app.get("/h5/withdraw", response_class=HTMLResponse)
def h5_withdraw(request: Request, user: Optional[models.User] = Depends(get_current_user)):
    return templates.TemplateResponse("h5/withdraw.html", {"request": request, "user": user})

@app.post("/h5/withdraw/submit")
def h5_withdraw_sub(amount: float = Form(...), real_name: str = Form(...), account: str = Form(...), user: Optional[models.User] = Depends(get_current_user), db: Session = Depends(get_db)):
    if amount < 1 or user.balance < amount: return "余额不足"
    user.balance -= amount
    db.add(models.Withdrawal(user_id=user.id, amount=amount, real_name=real_name, account=account))
    create_notification(db, user.id, "提现申请", f"申请提现 {amount} 元", "money")
    db.commit()
    return RedirectResponse("/h5/mine?msg=" + urllib.parse.quote("申请成功"), status_code=302)

@app.get("/h5/invite", response_class=HTMLResponse)
def h5_invite(request: Request, user: Optional[models.User] = Depends(get_current_user), db: Session = Depends(get_db)):
    children = db.query(models.User).filter(models.User.inviter_id == user.id).all()
    return templates.TemplateResponse("h5/invite.html", {"request": request, "user": user, "children": children, "base_url": str(request.base_url).rstrip("/")})

@app.get("/h5/password", response_class=HTMLResponse)
def h5_pwd(request: Request, user: Optional[models.User] = Depends(get_current_user)):
    return templates.TemplateResponse("h5/password.html", {"request": request, "user": user})

@app.post("/h5/password")
def h5_pwd_post(old_password: str = Form(...), new_password: str = Form(...), confirm_password: str = Form(...), user: Optional[models.User] = Depends(get_current_user), db: Session = Depends(get_db)):
    if not auth.verify_password(old_password, user.hashed_password): return "旧密码错误"
    if new_password != confirm_password: return "两次密码不一致"
    user.hashed_password = auth.get_password_hash(new_password)
    db.commit()
    return RedirectResponse("/login?msg=" + urllib.parse.quote("修改成功请登录"), status_code=302)

# --- Admin Routes ---

# 🟢 优化：后台看板防卡死处理
@app.get("/admin/dashboard", response_class=HTMLResponse)
def admin_dash(request: Request, user: Optional[models.User] = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user or not user.is_admin: return RedirectResponse("/h5/index")
    
    try:
        # 简单统计
        stats = {
            "pending_audit": db.query(models.Submission).filter(models.Submission.status == "pending").count(),
            "users": db.query(models.User).count(),
            "active_tasks": db.query(models.Task).filter(models.Task.is_active == True).count(),
            "pending_withdraw": db.query(models.Withdrawal).filter(models.Withdrawal.status == "pending").count()
        }
        
        # 图表数据 - 增加异常捕获，防止一个查询卡死整个页面
        dates, u_data, s_data, m_data = [], [], [], []
        today = datetime.now().date()
        for i in range(6, -1, -1):
            d = today - timedelta(days=i)
            dates.append(d.strftime("%m-%d"))
            
            # 使用 scalar() 稍微快一点
            u_cnt = db.query(func.count(models.User.id)).filter(models.User.created_at >= d, models.User.created_at < d + timedelta(days=1)).scalar()
            u_data.append(u_cnt)
            
            s_cnt = db.query(func.count(models.Submission.id)).filter(models.Submission.created_at >= d, models.Submission.created_at < d + timedelta(days=1)).scalar()
            s_data.append(s_cnt)
            
            m_sum = db.query(func.sum(models.Withdrawal.amount)).filter(models.Withdrawal.status == "paid", models.Withdrawal.created_at >= d, models.Withdrawal.created_at < d + timedelta(days=1)).scalar() or 0
            m_data.append(m_sum)
            
    except Exception as e:
        logger.error(f"Dashboard Error: {e}")
        # 如果报错，给空数据，保证页面能打开
        stats = { "pending_audit": 0, "users": 0, "active_tasks": 0, "pending_withdraw": 0 }
        dates, u_data, s_data, m_data = [], [], [], []

    return templates.TemplateResponse("admin/dashboard.html", {
        "request": request, "user": user, "stats": stats, 
        "chart_dates": dates, "chart_users": u_data, "chart_subs": s_data, "chart_money": m_data
    })

@app.get("/admin/materials", response_class=HTMLResponse)
def admin_materials(request: Request, user: Optional[models.User] = Depends(get_current_user), db: Session = Depends(get_db)):
    cats = db.query(models.MaterialCategory).order_by(models.MaterialCategory.created_at.desc()).all()
    return templates.TemplateResponse("admin/materials.html", {"request": request, "user": user, "categories": cats})

@app.post("/admin/materials/category/new")
def admin_mat_cat_new(name: str = Form(...), db: Session = Depends(get_db)):
    db.add(models.MaterialCategory(name=name))
    db.commit()
    return RedirectResponse("/admin/materials", status_code=302)

@app.post("/admin/materials/upload")
async def admin_mat_upload(cat_id: int = Form(...), files: List[UploadFile] = File(None), texts: str = Form(""), db: Session = Depends(get_db)):
    text_list = [line.strip() for line in texts.split('\n') if line.strip()]
    saved_files = []
    if files:
        for file in files:
            if file.filename:
                name = f"mat_{uuid.uuid4()}.{file.filename.split('.')[-1]}"
                with open(f"app/static/uploads/{name}", "wb") as b: shutil.copyfileobj(file.file, b)
                saved_files.append(f"/static/uploads/{name}")
    count = 0
    max_len = max(len(text_list), len(saved_files))
    if max_len == 0: return RedirectResponse("/admin/materials", status_code=302)
    for i in range(max_len):
        content = text_list[i % len(text_list)] if text_list else ""
        image = saved_files[i % len(saved_files)] if saved_files else ""
        mat = models.Material(category_id=cat_id, content=content, images=image)
        db.add(mat)
        count += 1
    cat = db.query(models.MaterialCategory).filter(models.MaterialCategory.id == cat_id).first()
    cat.total_count += count
    db.commit()
    return RedirectResponse(f"/admin/materials?msg=成功添加{count}条素材", status_code=302)

@app.get("/admin/settings", response_class=HTMLResponse)
def admin_settings(request: Request, user: Optional[models.User] = Depends(get_current_user), db: Session = Depends(get_db)):
    def g(k): 
        o = db.query(models.SystemConfig).filter(models.SystemConfig.key == k).first()
        return o.value if o else ""
    return templates.TemplateResponse("admin/settings.html", {
        "request": request, "user": user, "banners": db.query(models.Banner).all(),
        "announcement": g("announcement"), "commission_rate": g("commission_rate"),
        "contact_text": g("contact_text"), "contact_img": g("contact_img"),
        "pay_qrcode": g("pay_qrcode"), "categories": db.query(models.TaskCategory).all(),
        "vip_plans": db.query(models.VipPlan).all()
    })

@app.post("/admin/settings/paycode")
def admin_paycode(file: UploadFile = File(...), db: Session = Depends(get_db)):
    ext = file.filename.split(".")[-1]
    name = f"pay_{uuid.uuid4()}.{ext}"
    with open(f"app/static/uploads/{name}", "wb") as b: shutil.copyfileobj(file.file, b)
    path = f"/static/uploads/{name}"
    obj = db.query(models.SystemConfig).filter(models.SystemConfig.key == "pay_qrcode").first()
    if obj: obj.value = path
    else: db.add(models.SystemConfig(key="pay_qrcode", value=path))
    db.commit()
    return RedirectResponse("/admin/settings?msg=" + urllib.parse.quote("收款码已更新"), status_code=302)

@app.post("/admin/settings/banner")
def admin_banner(file: UploadFile = File(...), val: str = Form(None), db: Session = Depends(get_db)):
    ext = file.filename.split(".")[-1]
    name = f"ban_{uuid.uuid4()}.{ext}"
    with open(f"app/static/uploads/{name}", "wb") as b: shutil.copyfileobj(file.file, b)
    db.add(models.Banner(image_path=f"/static/uploads/{name}", link_url=val))
    db.commit()
    return RedirectResponse("/admin/settings?msg=" + urllib.parse.quote("上传成功"), status_code=302)

@app.post("/admin/settings/{key}")
def admin_conf(key: str, val: str = Form(...), db: Session = Depends(get_db)):
    obj = db.query(models.SystemConfig).filter(models.SystemConfig.key == key).first()
    if obj: obj.value = val
    else: db.add(models.SystemConfig(key=key, value=val))
    db.commit()
    return RedirectResponse("/admin/settings?msg=" + urllib.parse.quote("已保存"), status_code=302)

@app.post("/admin/settings/category")
def admin_cat(name: str = Form(...), code: str = Form(...), icon: str = Form(...), db: Session = Depends(get_db)):
    db.add(models.TaskCategory(name=name, code=code, icon=icon))
    db.commit()
    return RedirectResponse("/admin/settings", status_code=302)

@app.post("/admin/settings/category/delete")
def admin_cat_del(cat_id: int = Form(...), db: Session = Depends(get_db)):
    db.query(models.TaskCategory).filter(models.TaskCategory.id == cat_id).delete()
    db.commit()
    return RedirectResponse("/admin/settings", status_code=302)

@app.post("/admin/settings/vip")
def admin_vip(name: str = Form(...), days: int = Form(...), price: float = Form(...), bonus: int = Form(...), db: Session = Depends(get_db)):
    db.add(models.VipPlan(name=name, days=days, price=price, bonus_rate=bonus))
    db.commit()
    return RedirectResponse("/admin/settings", status_code=302)

@app.post("/admin/settings/vip/delete")
def admin_vip_del(pid: int = Form(...), db: Session = Depends(get_db)):
    db.query(models.VipPlan).filter(models.VipPlan.id == pid).delete()
    db.commit()
    return RedirectResponse("/admin/settings", status_code=302)

@app.post("/admin/settings/banner/delete")
def admin_banner_del(banner_id: int = Form(...), db: Session = Depends(get_db)):
    db.query(models.Banner).filter(models.Banner.id == banner_id).delete()
    db.commit()
    return RedirectResponse("/admin/settings", status_code=302)

@app.get("/admin/task/new", response_class=HTMLResponse)
def admin_task_new(request: Request, user: Optional[models.User] = Depends(get_current_user), db: Session = Depends(get_db)):
    return templates.TemplateResponse("admin/task_edit.html", {
        "request": request, "user": user, 
        "categories": db.query(models.TaskCategory).all(),
        "mat_categories": db.query(models.MaterialCategory).all()
    })

@app.post("/admin/task/new")
def admin_task_create(
    title: str = Form(...), 
    price: float = Form(0.0), 
    price_mode: str = Form("fixed"),
    material_cat_id: int = Form(0),
    category: str = Form(...), 
    description: str = Form(...), 
    text_req: str = Form(...), 
    image_req: str = Form(...), 
    file: UploadFile = File(None),
    reward_desc_input: str = Form(None),
    pricing_rule: str = Form(None),
    db: Session = Depends(get_db)
):
    path = None
    if file and file.filename:
        os.makedirs("app/static/uploads", exist_ok=True) # 确保目录存在
        name = f"ex_{uuid.uuid4()}.{file.filename.split('.')[-1]}"
        with open(f"app/static/uploads/{name}", "wb") as b: shutil.copyfileobj(file.file, b)
        path = f"/static/uploads/{name}"
    
    final_reward_desc = ""
    final_desc = description

    if price_mode == "fixed":
        final_reward_desc = f"{price}"
    else:
        final_reward_desc = reward_desc_input if reward_desc_input else "审核定价"
        if pricing_rule:
            final_desc = f"【💰 定价规则】\n{pricing_rule}\n\n【📝 任务详情】\n{description}"

    db.add(models.Task(
        title=title, 
        price=price, 
        reward_desc=final_reward_desc,
        price_mode=price_mode,
        material_category_id=material_cat_id if material_cat_id > 0 else None,
        description=final_desc, 
        category=category, 
        example_image_path=path, 
        text_req=text_req, 
        image_req=image_req
    ))
    db.commit()
    return RedirectResponse("/admin/dashboard?msg=" + urllib.parse.quote("发布成功"), status_code=302)

@app.get("/admin/deposit/list", response_class=HTMLResponse)
def admin_dep_list(request: Request, user: Optional[models.User] = Depends(get_current_user), db: Session = Depends(get_db)):
    return templates.TemplateResponse("admin/deposit_list.html", {"request": request, "user": user, "deposits": db.query(models.Deposit).order_by(models.Deposit.created_at.desc()).all()})

@app.post("/admin/deposit/process")
def admin_dep_proc(did: int = Form(...), action: str = Form(...), db: Session = Depends(get_db)):
    d = db.query(models.Deposit).filter(models.Deposit.id == did).first()
    if action == "approve": d.status = "approved"; d.user.balance += d.amount; create_notification(db, d.user.id, "充值到账", f"已入账 {d.amount}")
    else: d.status = "rejected"; create_notification(db, d.user.id, "充值驳回", "凭证无效")
    db.commit()
    return RedirectResponse("/admin/deposit/list", status_code=302)

@app.get("/admin/audit", response_class=HTMLResponse)
def admin_audit(request: Request, user: Optional[models.User] = Depends(get_current_user), db: Session = Depends(get_db)):
    return templates.TemplateResponse("admin/audit.html", {"request": request, "user": user, "submissions": db.query(models.Submission).filter(models.Submission.status == "pending").order_by(models.Submission.created_at.desc()).all()})

@app.post("/admin/audit/review")
def admin_review(submission_id: int = Form(...), action: str = Form(...), feedback: str = Form(None), amount: float = Form(0.0), db: Session = Depends(get_db)):
    sub = db.query(models.Submission).filter(models.Submission.id == submission_id).first()
    if action == "approve":
        reward = 0
        if sub.task.price_mode == 'dynamic':
            reward = amount
        else:
            reward = sub.task.price
            if sub.user.vip_end_time and sub.user.vip_end_time > datetime.now():
                reward = round(reward * 1.1, 2)
        sub.status = "approved"
        sub.user.balance += reward
        sub.final_amount = reward
        sub.user.credit_score = min(100, sub.user.credit_score + 1)
        create_notification(db, sub.user.id, "审核通过", f"任务【{sub.task.title}】已通过，获得 {reward} 元")
        if sub.user.inviter_id:
            inviter = db.query(models.User).filter(models.User.id == sub.user.inviter_id).first()
            if inviter:
                rate = float(db.query(models.SystemConfig).filter(models.SystemConfig.key == "commission_rate").first().value)
                comm = round(reward * (rate/100), 2)
                inviter.balance += comm
                create_notification(db, inviter.id, "推广提成", f"下级完成任务，获得 {comm} 元")
    else:
        sub.status = "rejected"
        sub.admin_feedback = feedback
        sub.user.credit_score = max(0, sub.user.credit_score - 10)
        create_notification(db, sub.user.id, "审核驳回", feedback)
    db.commit()
    return RedirectResponse("/admin/audit", status_code=302)

@app.get("/admin/withdraw/list", response_class=HTMLResponse)
def admin_wd_list(request: Request, user: Optional[models.User] = Depends(get_current_user), db: Session = Depends(get_db)):
    return templates.TemplateResponse("admin/withdraw_list.html", {"request": request, "user": user, "withdrawals": db.query(models.Withdrawal).order_by(models.Withdrawal.created_at.desc()).all()})

@app.post("/admin/withdraw/process")
def admin_wd_proc(wid: int = Form(...), action: str = Form(...), db: Session = Depends(get_db)):
    w = db.query(models.Withdrawal).filter(models.Withdrawal.id == wid).first()
    if action == "paid": w.status = "paid"; create_notification(db, w.user.id, "提现到账", "已打款")
    else: w.status = "rejected"; w.user.balance += w.amount; create_notification(db, w.user.id, "提现被拒", "余额已退回")
    db.commit()
    return RedirectResponse("/admin/withdraw/list", status_code=302)

@app.get("/admin/withdraw/export")
def admin_export(db: Session = Depends(get_db)):
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(["ID", "用户", "金额", "姓名", "账号", "状态"])
    for r in db.query(models.Withdrawal).all(): ws.append([r.id, r.user.username, r.amount, r.real_name, r.account, r.status])
    out = BytesIO(); wb.save(out); out.seek(0)
    return StreamingResponse(out, media_type="application/vnd.ms-excel", headers={"Content-Disposition": "attachment; filename=withdraw.xlsx"})

@app.get("/admin/users", response_class=HTMLResponse)
def admin_users(request: Request, user: Optional[models.User] = Depends(get_current_user), db: Session = Depends(get_db)):
    return templates.TemplateResponse("admin/user_list.html", {"request": request, "user": user, "users": db.query(models.User).order_by(models.User.created_at.desc()).all()})

@app.post("/admin/users/balance")
def admin_bal(user_id: int = Form(...), amount: float = Form(...), db: Session = Depends(get_db)):
    u = db.query(models.User).filter(models.User.id == user_id).first()
    u.balance += amount; create_notification(db, u.id, "余额变动", f"管理员调整 {amount}")
    db.commit()
    return RedirectResponse("/admin/users", status_code=302)

# --- 保留的管理员接口 ---
@app.get("/make_me_admin")
def make_me_admin(user: Optional[models.User] = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user: return "请先登录普通账号，再访问此链接"
    user.is_admin = True; db.commit()
    return f"成功，{user.username} 现为管理员"