from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text, DateTime, Float
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_admin = Column(Boolean, default=False)
    balance = Column(Float, default=0.0)
    inviter_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    avatar = Column(String, nullable=True)
    credit_score = Column(Integer, default=100)
    vip_end_time = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    
    submissions = relationship("Submission", back_populates="user")
    withdrawals = relationship("Withdrawal", back_populates="user")
    deposits = relationship("Deposit", back_populates="user")
    notifications = relationship("Notification", back_populates="user")
    assigned_materials = relationship("Material", back_populates="used_by_user")

class MaterialCategory(Base):
    __tablename__ = "material_categories"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    total_count = Column(Integer, default=0)
    used_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)
    
    materials = relationship("Material", back_populates="category", cascade="all, delete")

class Material(Base):
    __tablename__ = "materials"
    id = Column(Integer, primary_key=True, index=True)
    category_id = Column(Integer, ForeignKey("material_categories.id"))
    content = Column(Text) 
    images = Column(String) 
    status = Column(String, default="unused") 
    used_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    
    category = relationship("MaterialCategory", back_populates="materials")
    used_by_user = relationship("User", back_populates="assigned_materials")

class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    description = Column(Text)
    
    # 🟢 确保有这个字段：用于展示 "5-10元" 这种字符串
    reward_desc = Column(String) 
    
    price_mode = Column(String, default="fixed") 
    price = Column(Float, default=0.0)
    material_category_id = Column(Integer, ForeignKey("material_categories.id"), nullable=True)
    
    category = Column(String, default="other")
    example_image_path = Column(String, nullable=True)
    text_req = Column(String, default="none")
    image_req = Column(String, default="required")
    text_desc = Column(String, nullable=True)
    image_desc = Column(String, nullable=True)
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
    
    screenshot_path = Column(String, nullable=True)
    post_link = Column(String, nullable=True)
    status = Column(String, default="pending")
    admin_feedback = Column(String, nullable=True)
    final_amount = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.now)
    
    user = relationship("User", back_populates="submissions")
    task = relationship("Task", back_populates="submissions")
    material = relationship("Material")

# 以下表结构保持不变
class Withdrawal(Base):
    __tablename__ = "withdrawals"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    amount = Column(Float)
    real_name = Column(String)
    account = Column(String)
    status = Column(String, default="pending")
    admin_note = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    user = relationship("User", back_populates="withdrawals")

class Deposit(Base):
    __tablename__ = "deposits"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    amount = Column(Float)
    proof_img = Column(String)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.now)
    user = relationship("User", back_populates="deposits")

class Banner(Base):
    __tablename__ = "banners"
    id = Column(Integer, primary_key=True, index=True)
    image_path = Column(String)
    link_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.now)

class SystemConfig(Base):
    __tablename__ = "system_configs"
    key = Column(String, primary_key=True)
    value = Column(String)

class TaskCategory(Base):
    __tablename__ = "task_categories"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    code = Column(String, unique=True)
    icon = Column(String)
    color = Column(String, default="primary")
    sort_order = Column(Integer, default=0)

class VipPlan(Base):
    __tablename__ = "vip_plans"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    days = Column(Integer)
    price = Column(Float)
    bonus_rate = Column(Integer)

class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String)
    content = Column(String)
    type = Column(String, default="system")
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    user = relationship("User", back_populates="notifications")