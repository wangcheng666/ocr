# syntax=docker/dockerfile:1
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_HTTP_TIMEOUT=300 \
    UV_LINK_MODE=copy

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates gcc libgl1 fonts-noto-core fonts-noto-cjk fontconfig \
    && fc-cache -fv \
    && rm -rf /var/lib/apt/lists/*

# ── 安装 uv ──
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# ── 复制所有源码（含 MinerU workspace） ──
COPY pyproject.toml uv.lock ./
COPY MinerU/pyproject.toml MinerU/README.md MinerU/

# 先复制 MinerU 核心源码（常变），再复制业务代码
COPY MinerU/mineru/ MinerU/mineru/

# ── 安装依赖 ──
RUN uv sync --frozen --no-dev

# ── 复制业务代码 ──
COPY app/ app/

ENV MINERU_MODEL_SOURCE=local

EXPOSE 8000
CMD ["uv", "run", "python", "-m", "app.api.server"]
