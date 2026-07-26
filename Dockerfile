# fund-daily HF Spaces Dockerfile
# 基于 Python 3.11 slim 镜像（akshare 兼容性最好）

FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖（akshare 需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY . .

# 创建数据目录
RUN mkdir -p /app/data

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=app.py
ENV PORT=7860

# 暴露 HF Spaces 标准端口
EXPOSE 7860

# 健康检查
HEALTHCHECK --interval=30s --timeout=30s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:7860/api/status || exit 1

# 启动命令：先同步存储桶数据，再启动 Flask
CMD ["python", "-c", "from storage_sync import sync_from_bucket; sync_from_startup(); from app import app; import os; app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 7860)), debug=False)"]