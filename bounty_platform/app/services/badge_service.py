from sqlalchemy.orm import Session
from app import models

class BadgeService:
    @staticmethod
    def check_and_award(user: models.User, db: Session):
        """
        每次任务审核通过后调用，检查是否达成成就
        """
        # 1. 确保 medals 是列表
        if not user.medals: user.medals = []
        current_medals = set(user.medals) if isinstance(user.medals, list) else set()
        new_medals = []

        # 2. 判定逻辑
        # 成就A: 第一桶金 (余额累计超过 10 元) -> 实际场景建议记总收入字段，这里用余额近似
        if user.balance >= 10 and "first_gold" not in current_medals:
            new_medals.append("first_gold")
            db.add(models.Notification(user_id=user.id, title="恭喜获得勋章", content="达成成就【第一桶金】！"))

        # 成就B: 任务达人 (完成任务超过 10 单)
        completed_count = db.query(models.Submission).filter(
            models.Submission.user_id == user.id, 
            models.Submission.status == "approved"
        ).count()
        
        if completed_count >= 10 and "task_master" not in current_medals:
            new_medals.append("task_master")
            db.add(models.Notification(user_id=user.id, title="恭喜获得勋章", content="达成成就【任务达人】！"))

        # 3. 更新数据库
        if new_medals:
            # SQLAlchemy JSON 类型更新需要显式赋值
            updated_medals = list(current_medals.union(set(new_medals)))
            user.medals = updated_medals
            db.add(models.AuditLog(operator_id=0, action="system_grant", target_id=user.id, detail=f"自动颁发勋章: {new_medals}"))
            db.commit()