# 基于官方 python slim 镜像构建 FastAPI 后端
FROM python:3.11-slim

# 安装基础依赖
RUN apt-get update && apt-get install -y build-essential git && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制 Python 依赖列表
COPY ../../requirements.txt ./requirements.txt

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码（使用 .dockerignore 以减少上下文）
COPY ../../ .

# 设置环境变量 (生产应调整)
ENV PYTHONUNBUFFERED=1

EXPOSE 9999

# 默认启动命令 (也可以被 docker-compose 覆盖)
CMD ["uvicorn", "mag.main:app", "--host", "0.0.0.0", "--port", "9999", "--proxy-headers"]

