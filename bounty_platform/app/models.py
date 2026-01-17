from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)
    hashed_password = Column(String(255))
    avatar = Column(String(255))
    balance = Column(Float, default=0.0)
    credit_score = Column(Integer, default=100)
    
    # V3 Enterprise 新增字段
    is_admin = Column(Boolean, default=False)
    is_banned = Column(Boolean, default=False)  # 黑名单
    tags = Column(JSON, default=list)           # 用户标签 ["new", "vip"]
    medals = Column(JSON, default=list)         # 勋章 ["first_gold"]
    
    inviter_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    vip_end_time = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now())
    
    # 支付宝信息
    alipay_name = Column(String(50))
    alipay_account = Column(String(100))

class Material(Base):
    __tablename__ = "materials"
    id = Column(Integer, primary_key=True, index=True)
    category_id = Column(Integer, ForeignKey("material_categories.id"))
    title = Column(String(255))
    content = Column(Text)
    
    # V3: 支持多图与回收站
    images = Column(JSON)  # 存储 ["/path/1.jpg", "/path/2.jpg"]
    status = Column(String(20), default="unused") 
    is_deleted = Column(Boolean, default=False)   # 软删除
    deleted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now())

class MaterialCategory(Base):
    __tablename__ = "material_categories"
    id = Column(Integer, primary_key=True)
    name = Column(String(50))
    total_count = Column(Integer, default=0)
    used_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=func.now())

class Submission(Base):
    __tablename__ = "submissions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    task_id = Column(Integer, ForeignKey("tasks.id"))
    status = Column(String(20), default="pending") # pending, approved, rejected, appealing
    
    screenshot_path = Column(String(255))
    image_hash = Column(String(64))       # V3: MD5指纹
    
    admin_feedback = Column(String(255))
    appeal_reason = Column(String(255))   # V3: 申诉理由
    appeal_img = Column(String(255))      # V3: 申诉举证
    final_amount = Column(Float, default=0.0)
    created_at = Column(DateTime, default=func.now())
    
    user = relationship("User")
    task = relationship("Task")

class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True)
    title = Column(String(100))
    price = Column(Float)
    price_mode = Column(String(20), default="fixed")
    reward_desc = Column(String(100))
    description = Column(Text)
    category = Column(String(50))
    material_category_id = Column(Integer, nullable=True)
    required_tags = Column(JSON, nullable=True) # V3: 定向投放
    is_active = Column(Boolean, default=True)
    text_req = Column(String(20), default="none")
    image_req = Column(String(20), default="required")
    created_at = Column(DateTime, default=func.now())

class AuditLog(Base): # V3: 审计日志
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True)
    operator_id = Column(Integer)
    action = Column(String(50))
    target_id = Column(Integer)
    detail = Column(Text)
    ip_address = Column(String(50))
    created_at = Column(DateTime, default=func.now())

class CheckIn(Base): # V3: 签到表
    __tablename__ = "checkins"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    date = Column(String(20), index=True) 
    created_at = Column(DateTime, default=func.now())

# ...保留 Withdrawal, Deposit, Banner, SystemConfig, Notification, VipPlan, TaskCategory (结构保持不变)
# 为节省篇幅，此类基础表请沿用之前定义，确保继承自 Base 即可。
class Withdrawal(Base):
    __tablename__ = "withdrawals"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    amount = Column(Float)
    real_name = Column(String(50))
    account = Column(String(100))
    status = Column(String(20), default="pending")
    created_at = Column(DateTime, default=func.now())
    user = relationship("User")

class Deposit(Base):
    __tablename__ = "deposits"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    amount = Column(Float)
    proof_img = Column(String(255))
    status = Column(String(20), default="pending")
    created_at = Column(DateTime, default=func.now())
    user = relationship("User")

class Banner(Base):
    __tablename__ = "banners"
    id = Column(Integer, primary_key=True)
    image_path = Column(String(255))
    link_url = Column(String(255))
    created_at = Column(DateTime, default=func.now())

class SystemConfig(Base):
    __tablename__ = "system_configs"
    key = Column(String(50), primary_key=True)
    value = Column(Text)

class TaskCategory(Base):
    __tablename__ = "task_categories"
    id = Column(Integer, primary_key=True)
    name = Column(String(50))
    code = Column(String(50))
    icon = Column(String(255))
    color = Column(String(20))
    sort_order = Column(Integer, default=0)

class VipPlan(Base):
    __tablename__ = "vip_plans"
    id = Column(Integer, primary_key=True)
    name = Column(String(50))
    days = Column(Integer)
    price = Column(Float)
    bonus_rate = Column(Integer)

class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String(100))
    content = Column(Text)
    type = Column(String(20))
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())