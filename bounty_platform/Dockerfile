FROM python:3.9-slim
WORKDIR /app
RUN apt-get update && apt-get install -y libfreetype6-dev libjpeg-dev zlib1g-dev && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]