import logging
from app.database import SessionLocal
from app import models
from app.core import security

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_db():
    db = SessionLocal()
    try:
        # 1. 创建超级管理员
        admin_user = db.query(models.User).filter(models.User.username == "admin").first()
        if not admin_user:
            logger.info("Creating superuser 'admin' ...")
            admin_user = models.User(
                username="admin",
                hashed_password=security.get_password_hash("admin123"), # 默认密码
                is_admin=True,
                balance=8888.88
            )
            db.add(admin_user)
        
        # 2. 创建默认任务分类
        if db.query(models.TaskCategory).count() == 0:
            logger.info("Creating default task categories ...")
            cats = [
                models.TaskCategory(name="注册下载", code="reg", icon="📱", color="primary", sort_order=1),
                models.TaskCategory(name="电商绑卡", code="bank", icon="💳", color="success", sort_order=2),
                models.TaskCategory(name="试玩游戏", code="game", icon="🎮", color="warning", sort_order=3),
                models.TaskCategory(name="简单关注", code="follow", icon="❤️", color="danger", sort_order=4),
            ]
            db.add_all(cats)

        # 3. 创建默认素材分类
        if db.query(models.MaterialCategory).count() == 0:
            logger.info("Creating default material categories ...")
            db.add(models.MaterialCategory(name="新手必发朋友圈", total_count=0))

        # 4. 创建默认 VIP 套餐
        if db.query(models.VipPlan).count() == 0:
            logger.info("Creating default VIP plans ...")
            plans = [
                models.VipPlan(name="月卡会员", days=30, price=29.9, bonus_rate=10),
                models.VipPlan(name="季卡会员", days=90, price=79.9, bonus_rate=15),
                models.VipPlan(name="年卡至尊", days=365, price=199.9, bonus_rate=20),
            ]
            db.add_all(plans)

        db.commit()
        logger.info("✅ Initialization Completed! User: admin / Pass: admin123")
        
    except Exception as e:
        logger.error(f"Init failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    init_db()