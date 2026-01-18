from celery import Celery
from .core.config import settings

celery = Celery(
    "bounty_tasks",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
)

# 示例异步任务
@celery.task
def async_send_email(email: str, subject: str, content: str):
    import time
    time.sleep(2) # 模拟耗时
    print(f"📧 [模拟邮件] 发送给 {email}: {subject}")