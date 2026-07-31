# ======================================================================
# 多平台基础镜像参数（由 build-docker.sh 按架构传入）
#   amd64: BASE_IMAGE=python:3.13-slim  UV_IMAGE=ghcr.io/astral-sh/uv:0.7.13
#   arm64: BASE_IMAGE=python:3.13-slim-arm64  UV_IMAGE=ghcr.io/astral-sh/uv:0.7.13-arm64
# ======================================================================
ARG BASE_IMAGE=python:3.13-slim
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.7.13

# uv 工具阶段（多平台按架构选择 uv 镜像；用命名阶段让 COPY --from 引用静态阶段名）
FROM ${UV_IMAGE} AS uv-stage

# ======================================================================
# 阶段 1: BUILDER — 安装 Python 依赖（含 MinerU workspace member）
# ======================================================================
FROM ${BASE_IMAGE} AS builder

# 从 uv 阶段复制 uv/uvx（多平台按架构选择 uv 镜像）
COPY --from=uv-stage /uv /uvx /bin/

# pip 配置（内网源，作为 uv 的补充）
COPY .docker/.pip /root/.pip

# 系统依赖（用于 opencv、字体等运行时）
# 使用阿里云 HTTP 镜像源（内网环境 HTTPS 被中间人代理拦截，HTTP 可用）
RUN sed -i 's|http://deb.debian.org|http://mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null; \
    sed -i 's|http://deb.debian.org|http://mirrors.aliyun.com|g' /etc/apt/sources.list 2>/dev/null; \
    apt-get update 2>/dev/null || true; \
    apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 \
    fonts-noto-core fonts-noto-cjk fontconfig \
    || echo "apt install skipped (network unavailable)"; \
    fc-cache -fv 2>/dev/null || true; \
    rm -rf /var/lib/apt/lists/* 2>/dev/null; true

WORKDIR /app

# ── 第 1 层：只复制依赖声明文件 + 本地 wheel ──
# 利用 Docker 层缓存：pyproject.toml / uv.lock 不变时跳过此层
COPY uv.lock pyproject.toml /app/
COPY MinerU/pyproject.toml MinerU/README.md /app/MinerU/
COPY MinerU/mineru/version.py /app/MinerU/mineru/version.py
COPY packages/ /app/packages/

# 安装外部依赖（跳过 workspace member，安装为非 editable）
# --locked: 使用 uv.lock 中锁定的版本
# --find-links: 从 packages/ 找 wheel（离线构建）
# 多平台: 基础镜像和 uv 均为 multi-arch，--platform 支持 amd64/arm64
RUN uv sync --locked --no-install-project --no-editable \
    --find-links /app/packages/

# ── 第 2 层：复制 MinerU 源码，安装 workspace member ──
# --reinstall-package mineru: 强制重建 mineru（第 1 层只复制了 version.py，
#   uv 可能缓存了残缺 wheel；此处复制完整源码后必须强制重装）
COPY MinerU/mineru/ /app/MinerU/mineru/
COPY MinerU/LICENSE.md /app/MinerU/LICENSE.md
RUN uv sync --locked --no-editable \
    --reinstall-package mineru \
    --find-links /app/packages/

# ======================================================================
# 阶段 2: FINAL — 仅包含运行时所需的文件
# ======================================================================
FROM ${BASE_IMAGE}

# 构建参数
ARG VERSION
ARG BUILD_VERSION

# 环境变量
ENV APP_VERSION=${VERSION} \
    APP_BUILD_VERSION=${BUILD_VERSION} \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UVICORN_WORKERS=1

# 系统依赖（运行时必需）
# opencv-python(GUI版) 需要 X11 库: libxcb / libx11 / libxext 等
# 使用阿里云 HTTP 镜像源（内网环境 HTTPS 被中间人代理拦截，HTTP 可用）
RUN sed -i 's|http://deb.debian.org|http://mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null; \
    sed -i 's|http://deb.debian.org|http://mirrors.aliyun.com|g' /etc/apt/sources.list 2>/dev/null; \
    apt-get update 2>/dev/null || true; \
    apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 \
    libxcb1 libx11-6 libxext6 \
    libxrender1 libxi6 libxtst6 libxfixes3 libxrandr2 \
    fonts-noto-core fonts-noto-cjk fontconfig \
    || echo "apt install skipped (network unavailable)"; \
    fc-cache -fv 2>/dev/null || true; \
    rm -rf /var/lib/apt/lists/* 2>/dev/null; true

WORKDIR /app

# 从 builder 复制虚拟环境
COPY --from=builder /app/.venv /app/.venv

# 复制运行时所需的应用代码
COPY app/ /app/app/

# 模型目录挂载点
VOLUME /app/models

EXPOSE 8000

CMD ["/bin/bash", "-c", "source .venv/bin/activate && exec uvicorn app.api.server:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS}"]
