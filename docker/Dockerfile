FROM python:3.11-slim AS base

# 元信息
LABEL maintainer="Uniplore Team"
LABEL description="Uniplore Test Framework — 全维度工程化测试框架"

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    nodejs \
    npm \
    git \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY python_modules/requirements.txt /app/python_modules/requirements.txt
RUN pip install --no-cache-dir -r /app/python_modules/requirements.txt 2>/dev/null || true

# Node.js 依赖
COPY nodejs_modules/package.json /app/nodejs_modules/package.json
RUN cd /app/nodejs_modules && npm ci --production 2>/dev/null || true

# 复制框架代码
COPY test_framework/ /app/test_framework/
COPY config/ /app/config/ 2>/dev/null || true
COPY scripts/ /app/scripts/
COPY extensions/ /app/extensions/

# Playwright 浏览器（可选）
RUN playwright install --with-deps chromium 2>/dev/null || true

# 环境变量
ENV TF_ENV=test
ENV TF_LOG_LEVEL=INFO
ENV PYTHONPATH=/app

# 入口
ENTRYPOINT ["python", "-m", "test_framework"]
CMD ["--help"]
