from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text, DateTime, Float
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    # MySQL 索引字段需要指定长度
    username = Column(String(50), unique=True, index=True)
    hashed_password = Column(String(255))
    is_admin = Column(Boolean, default=False)
    balance = Column(Float, default=0.0)
    inviter_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    avatar = Column(String(255), nullable=True)
    credit_score = Column(Integer, default=100)
    vip_end_time = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    # 支付宝信息
    alipay_name = Column(String(50), nullable=True)
    alipay_account = Column(String(100), nullable=True)
    
    submissions = relationship("Submission", back_populates="user")
    withdrawals = relationship("Withdrawal", back_populates="user")
    deposits = relationship("Deposit", back_populates="user")
    notifications = relationship("Notification", back_populates="user")
    assigned_materials = relationship("Material", back_populates="used_by_user")
    children = relationship("User", backref="parent", remote_side=[id])

class MaterialCategory(Base):
    __tablename__ = "material_categories"
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    total_count = Column(Integer, default=0)
    used_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)
    
    materials = relationship("Material", back_populates="category", cascade="all, delete")

class Material(Base):
    __tablename__ = "materials"
    id = Column(Integer, primary_key=True, index=True)
    category_id = Column(Integer, ForeignKey("material_categories.id"))
    
    title = Column(String(255)) # 🟢 确认有标题字段
    content = Column(Text)      # 正文+标签
    images = Column(Text)       # 图片路径
    
    status = Column(String(20), default="unused") 
    used_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    
    category = relationship("MaterialCategory", back_populates="materials")
    used_by_user = relationship("User", back_populates="assigned_materials")

class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255))
    description = Column(Text)
    reward_desc = Column(String(100)) 
    price_mode = Column(String(20), default="fixed") 
    price = Column(Float, default=0.0)
    material_category_id = Column(Integer, ForeignKey("material_categories.id"), nullable=True)
    category = Column(String(50), default="other")
    example_image_path = Column(String(255), nullable=True)
    text_req = Column(String(20), default="none")
    image_req = Column(String(20), default="required")
    text_desc = Column(String(100), nullable=True)
    image_desc = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    
    submissions = relationship("Submission", back_populates="task")
    material_category = relationship("MaterialCategory")

class Submission(Base):
    __tablename__ = "submissions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    task_id = Column(Integer, ForeignKey("tasks.id"))
    assigned_material_id = Column(Integer, ForeignKey("materials.id"), nullable=True)
    screenshot_path = Column(String(255), nullable=True)
    post_link = Column(Text, nullable=True)
    status = Column(String(20), default="pending")
    admin_feedback = Column(Text, nullable=True)
    final_amount = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.now)
    
    user = relationship("User", back_populates="submissions")
    task = relationship("Task", back_populates="submissions")
    material = relationship("Material")

class Withdrawal(Base):
    __tablename__ = "withdrawals"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    amount = Column(Float)
    real_name = Column(String(50))
    account = Column(String(100))
    status = Column(String(20), default="pending")
    admin_note = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    user = relationship("User", back_populates="withdrawals")

class Deposit(Base):
    __tablename__ = "deposits"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    amount = Column(Float)
    proof_img = Column(String(255))
    status = Column(String(20), default="pending")
    created_at = Column(DateTime, default=datetime.now)
    user = relationship("User", back_populates="deposits")

class Banner(Base):
    __tablename__ = "banners"
    id = Column(Integer, primary_key=True, index=True)
    image_path = Column(String(255))
    link_url = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.now)

class SystemConfig(Base):
    __tablename__ = "system_configs"
    key = Column(String(50), primary_key=True)
    value = Column(Text)

class TaskCategory(Base):
    __tablename__ = "task_categories"
    id = Column(Integer, primary_key=True)
    name = Column(String(50))
    code = Column(String(50), unique=True)
    icon = Column(String(255))
    color = Column(String(20), default="primary")
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
    type = Column(String(20), default="system")
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    user = relationship("User", back_populates="notifications")