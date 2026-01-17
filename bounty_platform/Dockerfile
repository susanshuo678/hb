# 使用轻量级的 Python 3.9 版本
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 先拷贝依赖清单并安装（利用 Docker 缓存加速构建）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 拷贝整个项目代码
COPY . .

# 暴露端口
EXPOSE 8000

# 启动命令：运行 app 目录下的 main.py
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]