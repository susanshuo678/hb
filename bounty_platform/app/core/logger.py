import logging
from logging.handlers import TimedRotatingFileHandler
import os

def setup_logger():
    # 确保日志目录存在
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)

    logger = logging.getLogger("bounty_v3")
    logger.setLevel(logging.INFO)

    # 格式
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
    )

    # 1. 文件输出 (按天轮转，保留30天)
    file_handler = TimedRotatingFileHandler(
        filename=os.path.join(log_dir, "app.log"),
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    # 2. 控制台输出
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

logger = setup_logger()