# 基于官方 python slim 镜像构建 FastAPI 后端
FROM python:3.11-slim

# 安装基础依赖，安装后清理
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential git curl && \
    rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制 Python 依赖列表
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt && \
    apt-get purge -y --auto-remove build-essential && \
    rm -rf /root/.cache

# 复制项目代码（只复制必要的文件）
COPY mag ./mag
COPY __version__.py .

# 设置环境变量
ENV PYTHONUNBUFFERED=1

# 暴露端口
EXPOSE 9999

# 默认启动命令
CMD ["uvicorn", "mag.main:app", "--host", "0.0.0.0", "--port", "9999", "--proxy-headers"]

