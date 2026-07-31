#!/usr/bin/env bash
# ======================================================================
# 导出基础镜像到 .docker/images/（离线构建用）
# 用法: ./scripts/export-base-images.sh
# 在有网的机器上执行一次，把基础镜像打包保存
# ======================================================================
set -euo pipefail

cd "$(dirname "$0")/.."
mkdir -p .docker/images

echo "=========================================="
echo "导出基础镜像"
echo "=========================================="

# Python 基础镜像（amd64）
if docker image inspect python:3.13-slim >/dev/null 2>&1; then
    echo ">>> python:3.13-slim (amd64)..."
    docker save python:3.13-slim -o .docker/images/python313.tar
else
    echo "   未找到 python:3.13-slim，跳过（需先 docker pull）"
fi

# Python 基础镜像（arm64）
if docker image inspect python:3.13-slim-arm64 >/dev/null 2>&1; then
    echo ">>> python:3.13-slim-arm64..."
    docker save python:3.13-slim-arm64 -o .docker/images/python313-arm64.tar
else
    echo "   未找到 python:3.13-slim-arm64，跳过（arm64 构建需此镜像）"
fi

# uv 工具镜像（amd64）
if docker image inspect ghcr.io/astral-sh/uv:0.7.13 >/dev/null 2>&1; then
    echo ">>> uv:0.7.13 (amd64)..."
    docker save ghcr.io/astral-sh/uv:0.7.13 -o .docker/images/uv713.tar
else
    echo "   未找到 uv:0.7.13，跳过（需先 docker pull ghcr.io/astral-sh/uv:0.7.13）"
fi

# uv 工具镜像（arm64）
if docker image inspect ghcr.io/astral-sh/uv:0.7.13-arm64 >/dev/null 2>&1; then
    echo ">>> uv:0.7.13-arm64..."
    docker save ghcr.io/astral-sh/uv:0.7.13-arm64 -o .docker/images/uv713-arm64.tar
else
    echo "   未找到 uv:0.7.13-arm64，跳过"
fi

echo ""
echo "=========================================="
echo "导出完成!"
echo "=========================================="
ls -lh .docker/images/
echo ""
echo "注意: 构建前 build-docker.sh 会自动 docker load 这些镜像"
echo "      arm64 构建需要 python:3.13-slim-arm64，如缺失请先在有网机器拉取"
