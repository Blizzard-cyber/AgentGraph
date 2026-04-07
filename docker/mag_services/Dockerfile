# 构建阶段 - 安装依赖
FROM python:3.12-slim AS builder

# 安装构建依赖（添加重试机制）
RUN apt-get update -qq && \
    apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# 设置工作目录
WORKDIR /app

# 复制依赖列表
COPY requirements.txt .

# 安装 Python 依赖到虚拟环境
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir -U pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt && \
    find /opt/venv -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true && \
    find /opt/venv -type f -name "*.pyc" -delete

# 运行时阶段 - 只包含必要的文件
FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 从构建阶段复制虚拟环境
COPY --from=builder /opt/venv /opt/venv

# 设置环境变量
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/mag \
    PYTHONDONTWRITEBYTECODE=1

# 复制项目代码
COPY mag ./mag
COPY __version__.py .

# 暴露端口
EXPOSE 9999

# 默认启动命令
CMD ["uvicorn", "mag.main:app", "--host", "0.0.0.0", "--port", "9999", "--proxy-headers"]

