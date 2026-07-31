#!/usr/bin/env bash
# ======================================================================
# 多平台 Docker 镜像构建脚本（amd64 + arm64）
# 用法: ./scripts/build-multiarch.sh <VERSION>
# 示例: ./scripts/build-multiarch.sh v1.0.0
#
# 构建 amd64 + arm64 双平台镜像，推送到 REGISTRY 并合并 manifest
# 平台标签用 amd64 / arm64，不带 linux/ 前缀
#
# 说明:
#   - 各架构使用各自的基础镜像（python:3.13-slim / python:3.13-slim-arm64），
#     用默认 builder 分平台构建（容器化 buildx builder 看不到本地离线镜像）
#   - 需要 REGISTRY 环境变量（如 REGISTRY=registry.example.com/）推送合并
# ======================================================================
set -euo pipefail

cd "$(dirname "$0")/.."

IMAGE_NAME="${IMAGE_NAME:-ocr-server}"
VERSION="${1:?"错误: 请提供 VERSION 参数\n用法: $0 <VERSION>\n示例: $0 v1.0.0"}"
BUILD_VERSION=$(date +"%Y%m%d%H%M%S")
PLATFORMS="${PLATFORMS:-amd64,arm64}"
REGISTRY="${REGISTRY:?"错误: 多平台推送合并需要 REGISTRY 环境变量\n示例: REGISTRY=registry.example.com/ $0 v1.0.0"}"

echo "=========================================="
echo "多平台 Docker 镜像构建"
echo "=========================================="
echo "VERSION:       $VERSION"
echo "BUILD_VERSION: $BUILD_VERSION"
echo "IMAGE_NAME:    ${REGISTRY}${IMAGE_NAME}"
echo "PLATFORMS:     $PLATFORMS"
echo "=========================================="

# 预加载基础镜像（离线环境必须，避免去 registry 拉元数据）
if [ -d ".docker/images" ]; then
    echo ">>> 加载基础镜像..."
    for img in .docker/images/*.tar; do
        [ -f "$img" ] && docker load -i "$img"
    done
fi

# 架构 → 基础镜像
arch_base_image() {
    case "$1" in
        amd64) echo "python:3.13-slim" ;;
        arm64) echo "python:3.13-slim-arm64" ;;
        *) echo "" ;;
    esac
}
arch_uv_image() {
    case "$1" in
        amd64) echo "ghcr.io/astral-sh/uv:0.7.13" ;;
        arm64) echo "ghcr.io/astral-sh/uv:0.7.13-arm64" ;;
        *) echo "" ;;
    esac
}

FULL_IMAGE="${REGISTRY}${IMAGE_NAME}"
IFS=',' read -ra PLATFORM_LIST <<< "$PLATFORMS"
NUM=${#PLATFORM_LIST[@]}

# 每个平台单独构建 + 推送
for arch in "${PLATFORM_LIST[@]}"; do
    BASE_IMAGE=$(arch_base_image "$arch")
    UV_IMAGE=$(arch_uv_image "$arch")
    if [ -z "$BASE_IMAGE" ] || [ -z "$UV_IMAGE" ]; then
        echo "错误: 不支持的平台 '$arch'（可选: amd64, arm64）"
        exit 1
    fi

    echo ""
    echo ">>> 构建并推送 $arch ..."
    echo "    BASE_IMAGE: $BASE_IMAGE"
    echo "    UV_IMAGE:   $UV_IMAGE"

    docker buildx build \
        --pull=false \
        --platform "linux/$arch" \
        --build-arg VERSION="$VERSION" \
        --build-arg BUILD_VERSION="$BUILD_VERSION" \
        --build-arg BASE_IMAGE="$BASE_IMAGE" \
        --build-arg UV_IMAGE="$UV_IMAGE" \
        -t "${FULL_IMAGE}:${VERSION}-${arch}" \
        -t "${FULL_IMAGE}:latest-${arch}" \
        --push \
        .
done

# 合并多平台 manifest
echo ""
echo ">>> 合并多平台 manifest..."
if [ "$NUM" -eq 2 ]; then
    docker manifest create "${FULL_IMAGE}:${VERSION}" \
        "${FULL_IMAGE}:${VERSION}-${PLATFORM_LIST[0]}" "${FULL_IMAGE}:${VERSION}-${PLATFORM_LIST[1]}"
    docker manifest annotate "${FULL_IMAGE}:${VERSION}" "${FULL_IMAGE}:${VERSION}-${PLATFORM_LIST[0]}" --arch "${PLATFORM_LIST[0]}"
    docker manifest annotate "${FULL_IMAGE}:${VERSION}" "${FULL_IMAGE}:${VERSION}-${PLATFORM_LIST[1]}" --arch "${PLATFORM_LIST[1]}"
    docker manifest create "${FULL_IMAGE}:latest" \
        "${FULL_IMAGE}:latest-${PLATFORM_LIST[0]}" "${FULL_IMAGE}:latest-${PLATFORM_LIST[1]}"
    docker manifest annotate "${FULL_IMAGE}:latest" "${FULL_IMAGE}:latest-${PLATFORM_LIST[0]}" --arch "${PLATFORM_LIST[0]}"
    docker manifest annotate "${FULL_IMAGE}:latest" "${FULL_IMAGE}:latest-${PLATFORM_LIST[1]}" --arch "${PLATFORM_LIST[1]}"
    docker manifest push "${FULL_IMAGE}:${VERSION}"
    docker manifest push "${FULL_IMAGE}:latest"
else
    echo "⚠ 平台数 ($NUM) 不为 2，跳过 manifest 合并，仅保留各架构标签"
fi

echo ""
echo "=========================================="
echo "多平台镜像构建成功!"
echo "=========================================="
echo "镜像: ${FULL_IMAGE}:${VERSION} ($PLATFORMS)"
echo "=========================================="
