# ======================================================================
# 多平台 Dockerfile（参考 czce-ai-platform）
# 基础镜像选择放在 Dockerfile 内部：构建时仅需传入 --build-arg TARGETARCH=amd64|arm64
#   amd64: python:3.13-slim-ocr        + uv:0.7.13
#   arm64: python:3.13-slim-ocr-arm64  + uv:0.7.13-arm64
# 基础镜像为预烤镜像（已含系统依赖+字体），构建完全离线
# 新增架构只需在此处增加对应的命名阶段，无需改动构建脚本
# ======================================================================
ARG TARGETARCH=amd64

# 架构对应的 Python 基础镜像（命名阶段，由 TARGETARCH 选择）
# 使用预烤镜像 python:3.13-slim-ocr{-arm64}（已含系统依赖+字体），构建完全离线
FROM python:3.13-slim-ocr AS python-base-amd64
FROM python:3.13-slim-ocr-arm64 AS python-base-arm64
FROM python-base-${TARGETARCH} AS python-base

# uv 工具镜像（按架构选择；用命名阶段让 COPY --from 引用静态阶段名）
FROM ghcr.io/astral-sh/uv:0.7.13 AS uv-bin-amd64
FROM ghcr.io/astral-sh/uv:0.7.13-arm64 AS uv-bin-arm64
FROM uv-bin-${TARGETARCH} AS uv-bin

# ======================================================================
# 阶段 1: BUILDER — 安装 Python 依赖（含 MinerU workspace member）
# ======================================================================
FROM python-base AS builder

ARG TARGETARCH

# 从 uv 阶段复制 uv/uvx（按架构选择）
COPY --from=uv-bin /uv /uvx /bin/

# pip 配置（内网源，作为 uv 的补充）
COPY .docker/.pip /root/.pip

WORKDIR /app

# ── 第 1 层：只复制依赖声明文件 + 本地 wheel ──
# 利用 Docker 层缓存：pyproject.toml / uv.lock 不变时跳过此层
COPY uv.lock pyproject.toml /app/
COPY MinerU/pyproject.toml MinerU/README.md /app/MinerU/
COPY MinerU/mineru/version.py /app/MinerU/mineru/version.py
COPY packages/ /app/packages/

# 安装外部依赖（跳过 workspace member，安装为非 editable）
# --locked: 使用 uv.lock 中锁定的版本
# --offline: 强制离线（lock 已指向本地 packages/，见 docs/离线构建操作文档.md）
# --find-links: 从 packages/ 找 wheel
# 多平台: 基础镜像和 uv 均为 multi-arch，同一份锁覆盖 amd64/arm64
RUN uv sync --locked --offline --no-install-project --no-editable \
    --find-links /app/packages/

# ── 第 2 层：复制 MinerU 源码，安装 workspace member ──
# --reinstall-package mineru: 强制重建 mineru（第 1 层只复制了 version.py，
#   uv 可能缓存了残缺 wheel；此处复制完整源码后必须强制重装）
COPY MinerU/mineru/ /app/MinerU/mineru/
COPY MinerU/LICENSE.md /app/MinerU/LICENSE.md
RUN uv sync --locked --offline --no-editable \
    --reinstall-package mineru \
    --find-links /app/packages/

# ======================================================================
# 阶段 2: FINAL — 仅包含运行时所需的文件
# ======================================================================
FROM python-base

# 构建参数
ARG VERSION
ARG BUILD_VERSION

# 环境变量
ENV APP_VERSION=${VERSION} \
    APP_BUILD_VERSION=${BUILD_VERSION} \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UVICORN_WORKERS=1

WORKDIR /app

# 从 builder 复制虚拟环境
COPY --from=builder /app/.venv /app/.venv

# 复制运行时所需的应用代码
COPY app/ /app/app/

# 资源（configs + models）不打进镜像，运行期由宿主机 ./resources 挂载到 /app/resources

EXPOSE 80

CMD ["/bin/bash", "-c", "source .venv/bin/activate && exec uvicorn app.api.server:app --host 0.0.0.0 --port 80 --workers ${UVICORN_WORKERS}"]
