# Kimi Gateway Dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY app/ ./app/
COPY .env* ./

# 暴露端口
EXPOSE 8765

# 启动命令
CMD ["python", "app/main.py"]
