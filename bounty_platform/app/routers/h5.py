from fastapi import APIRouter, Depends, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from datetime import datetime, timedelta
import os, uuid, shutil
from fastapi_limiter.depends import RateLimiter

from ..database import get_db, redis_conn
from .. import models
from ..core import deps, security, logger
from ..services.risk_control import RiskControlService, save_upload_file_sync
from ..services.poster_service import PosterService

router = APIRouter(prefix="/h5", tags=["H5"])
templates = Jinja2Templates(directory="app/templates")

# 1. 首页 (🟢 修复：增加标签可见性过滤)
@router.get("/index")
def h5_index(request: Request, cat: str = "all", db: Session = Depends(get_db)):
    # 尝试获取当前用户（可选，游客也可访问）
    token = request.cookies.get("access_token")
    current_user = None
    if token:
        try:
            scheme, param = token.split()
            if scheme.lower() == 'bearer':
                # 这里简单复用 deps 逻辑，实际建议拆分 get_current_user_optional
                # 为简化代码，此处仅在有 token 时尝试解析，解析失败不报错
                from jose import jwt
                from ..core.config import settings
                payload = jwt.decode(param, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
                username = payload.get("sub")
                current_user = db.query(models.User).filter(models.User.username == username).first()
        except:
            pass

    banners = db.query(models.Banner).all()
    conf_q = db.query(models.SystemConfig)
    announcement = conf_q.filter(models.SystemConfig.key == "announcement").first()
    announcement = announcement.value if announcement else "欢迎来到红白悬赏 V3.0"
    popup = conf_q.filter(models.SystemConfig.key == "popup_content").first()
    popup_content = popup.value if popup else ""

    # 任务查询
    query = db.query(models.Task).filter(models.Task.is_active == True)
    if cat != "all":
        query = query.filter(models.Task.category == cat)
    
    tasks_all = query.order_by(models.Task.created_at.desc()).all()
    
    # 🟢 过滤逻辑：如果任务有 required_tags，用户必须包含其中至少一个 tag 才能看到
    visible_tasks = []
    user_tags = set(current_user.tags if current_user and current_user.tags else [])
    
    for t in tasks_all:
        if not t.required_tags or len(t.required_tags) == 0:
            visible_tasks.append(t)
        else:
            # 任务有门槛，检查用户
            req_tags = set(t.required_tags)
            if current_user and (user_tags & req_tags): # 有交集
                visible_tasks.append(t)
            # 游客不可见带标签的任务
            
    return templates.TemplateResponse("h5/index.html", {
        "request": request, "banners": banners, "announcement": announcement,
        "popup_content": popup_content, "categories": db.query(models.TaskCategory).order_by(models.TaskCategory.sort_order).all(),
        "current_cat": cat, "tasks": visible_tasks
    })
# 🟢 2. 新增：账单明细页
@router.get("/bill")
def h5_bill(request: Request, db: Session = Depends(get_db), user=Depends(deps.get_current_user)):
    # 聚合查询：由于没有统一 Transaction 表，我们需要从各表聚合数据并按时间排序
    # 这在 V3 是一个折中方案，V4 建议重构为统一流水表
    
    bills = []
    
    # 1. 任务收入
    subs = db.query(models.Submission).filter(models.Submission.user_id == user.id, models.Submission.status == "approved").all()
    for s in subs:
        bills.append({"type": "income", "title": f"任务奖励: {s.task.title}", "amount": s.final_amount, "time": s.created_at}) # 注意这里用 created_at 近似
        
    # 2. 提现支出
    wds = db.query(models.Withdrawal).filter(models.Withdrawal.user_id == user.id).all()
    for w in wds:
        if w.status == "pending":
            bills.append({"type": "expense", "title": "提现申请 (审核中)", "amount": -w.amount, "time": w.created_at})
        elif w.status == "paid":
            bills.append({"type": "expense", "title": "提现成功", "amount": -w.amount, "time": w.created_at})
        elif w.status == "rejected":
            bills.append({"type": "info", "title": "提现驳回 (退款)", "amount": 0, "time": w.created_at}) # 余额未动，或者设计为先扣后退
            
    # 3. 充值收入
    deps_list = db.query(models.Deposit).filter(models.Deposit.user_id == user.id, models.Deposit.status == "approved").all()
    for d in deps_list:
        bills.append({"type": "income", "title": "余额充值", "amount": d.amount, "time": d.created_at})

    # 4. VIP 购买 (通过 AuditLog 查)
    logs = db.query(models.AuditLog).filter(models.AuditLog.operator_id == user.id, models.AuditLog.action == "buy_vip").all()
    for l in logs:
        # 解析金额，这里简单处理
        import re
        match = re.search(r"花费 (\d+(\.\d+)?) 元", l.detail)
        cost = float(match.group(1)) if match else 0
        bills.append({"type": "expense", "title": "购买VIP会员", "amount": -cost, "time": l.created_at})
        
    # 按时间倒序
    bills.sort(key=lambda x: x["time"], reverse=True)
    
    return templates.TemplateResponse("h5/bill.html", {"request": request, "bills": bills})
# 2. 🟢 新增：提交申诉接口
# 🟢 2. 抢单接口 (核心升级：Redis 锁 + 限流)
@router.post("/task/{task_id}/grab", dependencies=[Depends(RateLimiter(times=1, seconds=3))]) # 3秒防抖
async def grab_task(task_id: int, db: Session = Depends(get_db), user=Depends(deps.get_current_active_user)):
    # 🟢 Redis 分布式锁：防止超卖
    # 锁的 Key 基于 task_id，锁 5 秒自动释放
    lock_key = f"lock:grab_task:{task_id}"
    have_lock = await redis_conn.set(lock_key, "1", nx=True, ex=5)
    
    if not have_lock:
        return Response(content="系统繁忙，请稍后重试", status_code=429)

    try:
        task = db.query(models.Task).filter(models.Task.id == task_id).first()
        if not task: return RedirectResponse(f"/h5/task/{task_id}")
        
        # 检查是否已领
        exists = db.query(models.Submission).filter(models.Submission.user_id == user.id, models.Submission.task_id == task_id).first()
        if exists: return RedirectResponse(f"/h5/task/{task_id}")

        new_sub = models.Submission(user_id=user.id, task_id=task_id, status="pending")
        
        # 素材扣减逻辑
        if task.material_category_id:
            # 查找未使用的素材
            mat = db.query(models.Material).with_for_update().filter( # MySQL 行锁双重保险
                models.Material.category_id == task.material_category_id,
                models.Material.status == "unused",
                models.Material.is_deleted == False
            ).first()
            
            if mat:
                mat.status = "locked"
                mat.used_by_user_id = user.id
                mat.used_at = datetime.now()
                new_sub.assigned_material_id = mat.id
                
                cat = db.query(models.MaterialCategory).filter(models.MaterialCategory.id == mat.category_id).first()
                if cat: cat.used_count += 1
            else:
                # 没素材了，释放锁并提示
                await redis_conn.delete(lock_key)
                return Response(content="手慢了，素材已被抢光！", media_type="text/plain")
        
        db.add(new_sub)
        db.commit()
        logger.info(f"User {user.id} grabbed task {task_id}")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Grab failed: {e}")
        return Response(content="抢单失败，请重试", media_type="text/plain")
    finally:
        # 释放锁
        await redis_conn.delete(lock_key)

    return RedirectResponse(f"/h5/task/{task_id}", status_code=302)
    
# 3. 任务详情
@router.get("/task/{task_id}")
def h5_task_detail(task_id: int, request: Request, db: Session = Depends(get_db), user=Depends(deps.get_current_user)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task: return RedirectResponse("/h5/index")
    
    # 检查是否已提交
    existing_sub = db.query(models.Submission).filter(
        models.Submission.user_id == user.id,
        models.Submission.task_id == task_id
    ).first()
    
    # 检查是否有关联素材
    assigned_material = None
    if existing_sub and existing_sub.assigned_material_id:
        assigned_material = db.query(models.Material).filter(models.Material.id == existing_sub.assigned_material_id).first()
        
    return templates.TemplateResponse("h5/detail.html", {
        "request": request, "task": task, "user": user,
        "existing_sub": existing_sub, "assigned_material": assigned_material
    })

# 4. 提交任务 (含 V3 风控)
@router.post("/task/{task_id}/submit")
def submit_task(
    task_id: int,
    file: UploadFile = File(...),
    post_link: str = Form(None),
    db: Session = Depends(get_db),
    user=Depends(deps.get_current_active_user)
):
    # 1. 保存图片
    saved_rel_path = save_upload_file_sync(file)
    if not saved_rel_path:
        return {"code": 500, "message": "文件保存失败"}
    
    full_path = f"app{saved_rel_path}" # 补全相对路径用于读取
    
    # 2. 🛑 风控：MD5 查重
    md5_val = RiskControlService.calculate_file_md5(full_path)
    if RiskControlService.is_duplicate_image(db, md5_val):
        return {"code": 400, "message": "❌ 系统检测到重复截图，请勿作弊！"}
    
    # 3. 入库
    # 查找之前的 Submission 记录（因为可能是先领素材后提交）
    sub = db.query(models.Submission).filter(
        models.Submission.user_id == user.id, 
        models.Submission.task_id == task_id
    ).first()
    
    if not sub:
        # 如果是直接提交的任务
        sub = models.Submission(user_id=user.id, task_id=task_id)
        db.add(sub)
    
    sub.screenshot_path = saved_rel_path
    sub.image_hash = md5_val
    sub.status = "pending"
    # 如果任务需要链接
    if post_link: 
        sub.appeal_reason = post_link # 暂存到备用字段，或者新建字段
        
    db.commit()
    return {"code": 200, "message": "✅ 提交成功，等待审核"}

# 5. 抢单/领取素材接口
@router.post("/task/{task_id}/grab")
def grab_task(task_id: int, db: Session = Depends(get_db), user=Depends(deps.get_current_active_user)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task: return RedirectResponse(f"/h5/task/{task_id}")
    
    # 创建初始 Submission 记录
    new_sub = models.Submission(user_id=user.id, task_id=task_id, status="processing")
    
    # 如果任务绑定了素材库
    if task.material_category_id:
        # 找一个未使用的素材
        mat = db.query(models.Material).filter(
            models.Material.category_id == task.material_category_id,
            models.Material.status == "unused",
            models.Material.is_deleted == False
        ).first()
        
        if mat:
            mat.status = "locked" # 锁定
            new_sub.assigned_material_id = mat.id
            # 更新分类统计
            cat = db.query(models.MaterialCategory).filter(models.MaterialCategory.id == mat.category_id).first()
            if cat: cat.used_count += 1
    
    db.add(new_sub)
    db.commit()
    return RedirectResponse(f"/h5/task/{task_id}", status_code=302)

# 6. 排行榜
@router.get("/rank")
def h5_rank(request: Request, db: Session = Depends(get_db)):
    # 富豪榜
    rich_list = db.query(models.User).order_by(models.User.balance.desc()).limit(10).all()
    # 勤奋榜 (提交任务数)
    diligence_list = db.query(models.User, func.count(models.Submission.id).label("count"))\
        .join(models.Submission)\
        .group_by(models.User.id)\
        .order_by(func.count(models.Submission.id).desc())\
        .limit(10).all()
        
    return templates.TemplateResponse("h5/rank.html", {
        "request": request, "rich_list": rich_list, "diligence_list": diligence_list
    })

# 7. 充值页面
@router.get("/recharge")
def h5_recharge(request: Request, db: Session = Depends(get_db), user=Depends(deps.get_current_user)):
    conf = db.query(models.SystemConfig).filter(models.SystemConfig.key == "pay_qrcode").first()
    pay_qrcode = conf.value if conf else ""
    return templates.TemplateResponse("h5/recharge.html", {"request": request, "user": user, "pay_qrcode": pay_qrcode})

@router.post("/recharge/submit")
def h5_recharge_submit(amount: float = Form(...), file: UploadFile = File(...), db: Session = Depends(get_db), user=Depends(deps.get_current_active_user)):
    path = save_upload_file_sync(file)
    deposit = models.Deposit(user_id=user.id, amount=amount, proof_img=path)
    db.add(deposit)
    db.commit()
    return {"code": 200, "message": "提交成功，等待财务审核"}

# 8. 提现页面
@router.get("/withdraw")
def h5_withdraw(request: Request, user=Depends(deps.get_current_user)):
    return templates.TemplateResponse("h5/withdraw.html", {"request": request, "user": user})

@router.post("/withdraw/submit")
def h5_withdraw_submit(amount: float = Form(...), real_name: str = Form(...), account: str = Form(...), db: Session = Depends(get_db), user=Depends(deps.get_current_active_user)):
    if user.balance < amount:
        return {"code": 400, "message": "余额不足"}
    if amount < 1:
        return {"code": 400, "message": "最低提现 1 元"}
        
    # 扣余额
    user.balance -= amount
    user.alipay_name = real_name # 更新用户的支付宝信息
    user.alipay_account = account
    
    wd = models.Withdrawal(user_id=user.id, amount=amount, real_name=real_name, account=account)
    db.add(wd)
    db.commit()
    return RedirectResponse("/h5/mine", status_code=302)

# 9. 消息中心
@router.get("/messages")
def h5_messages(request: Request, db: Session = Depends(get_db), user=Depends(deps.get_current_user)):
    notifications = db.query(models.Notification).filter(models.Notification.user_id == user.id).order_by(models.Notification.created_at.desc()).all()
    # 标记全部已读
    for n in notifications: n.is_read = True
    db.commit()
    return templates.TemplateResponse("h5/messages.html", {"request": request, "notifications": notifications})

# 10. 邀请页
@router.get("/invite")
def h5_invite(request: Request, db: Session = Depends(get_db), user=Depends(deps.get_current_user)):
    children = db.query(models.User).filter(models.User.inviter_id == user.id).order_by(models.User.created_at.desc()).all()
    # 拼接基础URL
    base_url = str(request.base_url).rstrip("/")
    return templates.TemplateResponse("h5/invite.html", {"request": request, "user": user, "children": children, "base_url": base_url})
    
@router.get("/invite/poster", dependencies=[Depends(RateLimiter(times=5, seconds=60))])
def get_my_poster(request: Request, user=Depends(deps.get_current_user)):
    base_url = str(request.base_url).rstrip("/")
    img_bytes = PosterService.generate_poster(user.id, user.username, base_url)
    return Response(content=img_bytes, media_type="image/jpeg")
    
# 11. VIP页面
@router.get("/vip")
def h5_vip(request: Request, db: Session = Depends(get_db), user=Depends(deps.get_current_user)):
    plans = db.query(models.VipPlan).all()
    is_vip = user.vip_end_time and user.vip_end_time > datetime.now()
    return templates.TemplateResponse("h5/vip.html", {"request": request, "user": user, "plans": plans, "is_vip": is_vip})

@router.post("/vip/buy")
def h5_vip_buy(plan_id: int = Form(...), db: Session = Depends(get_db), user=Depends(deps.get_current_active_user)):
    plan = db.query(models.VipPlan).filter(models.VipPlan.id == plan_id).first()
    if not plan: return {"code": 400, "message": "套餐不存在"}
    
    if user.balance < plan.price:
        return {"code": 400, "message": "余额不足，请充值"}
    
    # 扣款
    user.balance -= plan.price
    
    # 🟢 修复逻辑：计算过期时间
    now = datetime.now()
    if user.vip_end_time and user.vip_end_time > now:
        # 如果已经是 VIP，在原有时间上续期
        user.vip_end_time += timedelta(days=plan.days)
    else:
        # 如果不是 VIP，从现在开始算
        user.vip_end_time = now + timedelta(days=plan.days)
    
    # 记录日志
    db.add(models.AuditLog(operator_id=user.id, action="buy_vip", detail=f"购买套餐 {plan.name}，花费 {plan.price} 元"))
    db.commit()
    
    return RedirectResponse("/h5/vip", status_code=302)

@router.get("/mine")
def h5_mine(request: Request, db: Session = Depends(get_db), user=Depends(deps.get_current_user)):
    # ... 原有代码 ...
    unread_count = db.query(models.Notification).filter(models.Notification.user_id == user.id, models.Notification.is_read == False).count()
    subs = db.query(models.Submission).filter(models.Submission.user_id == user.id).order_by(models.Submission.created_at.desc()).limit(20).all()
    return templates.TemplateResponse("h5/mine.html", {
        "request": request, "user": user, "now": datetime.now(),
        "unread_count": unread_count, "submissions": subs
    })

# 12. 设置页面 (修改头像等)
@router.get("/settings")
def h5_settings(request: Request, user=Depends(deps.get_current_user)): 
    return templates.TemplateResponse("h5/settings.html", {"request": request, "user": user})

@router.post("/settings/avatar")
def h5_update_avatar(file: UploadFile = File(...), db: Session = Depends(get_db), user=Depends(deps.get_current_user)):
    path = save_upload_file_sync(file)
    user.avatar = path
    db.commit()
    return {"code": 200, "message": "头像修改成功"}

# 13. 修改密码
@router.get("/password")
def h5_password(request: Request, user=Depends(deps.get_current_user)): 
    return templates.TemplateResponse("h5/password.html", {"request": request, "user": user})

@router.post("/password")
def h5_password_submit(
    old_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
    user=Depends(deps.get_current_user)
):
    if not security.verify_password(old_password, user.hashed_password):
        return templates.TemplateResponse("h5/password.html", {"request": request, "user": user, "error": "旧密码错误"})
    
    if new_password != confirm_password:
        return templates.TemplateResponse("h5/password.html", {"request": request, "user": user, "error": "两次新密码不一致"})
        
    user.hashed_password = security.get_password_hash(new_password)
    db.commit()
    
    return RedirectResponse("/login", status_code=302)
    
    
    
@router.get("/faq")
def h5_faq(request: Request):
    # 可以在 system_configs 表里存 JSON，这里先硬编码演示
    faqs = [
        {"q": "如何提现？", "a": "满1元即可提现到支付宝，24小时内到账。"},
        {"q": "审核需要多久？", "a": "一般在 10-30 分钟内完成，夜间可能延迟。"},
        {"q": "为什么任务被驳回？", "a": "请查看驳回理由，通常是因为截图不清晰或未达标。"}
    ]
    return templates.TemplateResponse("h5/faq.html", {"request": request, "faqs": faqs})