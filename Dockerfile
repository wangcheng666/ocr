FROM docker.m.daocloud.io/library/python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
    PIP_NO_CACHE_DIR=1

# 系统依赖 (TUNA mirror)
RUN sed -i 's|http://deb.debian.org|https://mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null; \
    sed -i 's|http://deb.debian.org|https://mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list 2>/dev/null; \
    apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 \
    fonts-noto-core fonts-noto-cjk fontconfig \
    && fc-cache -fv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先复制依赖声明文件，利用缓存
COPY pyproject.toml ./
COPY MinerU/pyproject.toml MinerU/README.md MinerU/
COPY MinerU/mineru/ MinerU/mineru/

# pip 安装依赖（仅使用预编译 wheel，跳过源码编译）
RUN pip install --only-binary :all: \
    fastapi uvicorn[standard] python-multipart python-dotenv \
    "latex2mathml>=3.81.0" "mathml2omml>=0.0.2" \
    && pip install -e ./MinerU

COPY app/ app/

ENV MINERU_MODEL_SOURCE=local

EXPOSE 8000
CMD ["python", "-m", "app.api.server"]
