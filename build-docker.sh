#!/usr/bin/env bash
# ======================================================================
# Docker 构建脚本（支持多平台 amd64/arm64）
# 用法: ./build-docker.sh <VERSION> [PLATFORM]
# 示例: ./build-docker.sh v1.0.0              # 默认当前架构
# 示例: ./build-docker.sh v1.0.0 amd64        # 指定 amd64
# 示例: ./build-docker.sh v1.0.0 arm64        # 指定 arm64
# 示例: ./build-docker.sh v1.0.0 amd64,arm64  # 多平台
# 平台标签用 amd64 / arm64，不带 linux/ 前缀
#
# 多平台说明:
#   - 每个平台使用各自的基础镜像（python:3.13-slim / python:3.13-slim-arm64）
#   - 单平台: 打 {VERSION} + latest 标签
#   - 多平台: 各架构打 {VERSION}-{arch} 标签；设置 REGISTRY 时推送到仓库并合并 manifest
# ======================================================================
set -euo pipefail

cd "$(dirname "$0")"

IMAGE_NAME="${IMAGE_NAME:-ocr-server}"
VERSION="${1:?"错误: 请提供 VERSION 参数\n用法: $0 <VERSION> [PLATFORM]\n示例: $0 v1.0.0"}"
PLATFORM_ARG="${2:-}"
PLATFORM="${PLATFORM_ARG:-}"
REGISTRY="${REGISTRY:-}"   # 例如: registry.example.com/（推送+合并 manifest 用）
BUILD_VERSION=$(date +"%Y%m%d%H%M%S")

# 默认平台 = 当前机器架构（未显式指定时打 {VERSION}/latest 标签）
if [ -z "$PLATFORM" ]; then
    case "$(uname -m)" in
        x86_64|amd64) PLATFORM="amd64" ;;
        aarch64|arm64) PLATFORM="arm64" ;;
        *) echo "错误: 未知架构 $(uname -m)"; exit 1 ;;
    esac
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

echo "=========================================="
echo "开始构建 Docker 镜像"
echo "=========================================="
echo "VERSION:       $VERSION"
echo "BUILD_VERSION: $BUILD_VERSION"
echo "IMAGE_NAME:    ${REGISTRY}${IMAGE_NAME}"
echo "PLATFORM:      $PLATFORM"
[ -n "$REGISTRY" ] && echo "REGISTRY:      $REGISTRY"
echo "=========================================="

# 预加载基础镜像（离线环境必须，避免去 registry 拉元数据）
if [ -d ".docker/images" ]; then
    echo ">>> 加载基础镜像..."
    for img in .docker/images/*.tar; do
        [ -f "$img" ] && docker load -i "$img"
    done
fi

# 解析平台列表
IFS=',' read -ra PLATFORMS <<< "$PLATFORM"
NUM=${#PLATFORMS[@]}

# 每个平台单独构建（各自的基础镜像不同，无法用单次 --platform a,b）
for arch in "${PLATFORMS[@]}"; do
    BASE_IMAGE=$(arch_base_image "$arch")
    UV_IMAGE=$(arch_uv_image "$arch")
    if [ -z "$BASE_IMAGE" ] || [ -z "$UV_IMAGE" ]; then
        echo "错误: 不支持的平台 '$arch'（可选: amd64, arm64）"
        exit 1
    fi

    echo ""
    echo ">>> 构建 $arch ..."
    echo "    BASE_IMAGE: $BASE_IMAGE"
    echo "    UV_IMAGE:   $UV_IMAGE"

    # 标签策略:
    #   - 未显式指定平台（默认当前架构）→ 打 {VERSION}/latest 正式标签
    #   - 显式指定平台（单/多）→ 打 {VERSION}-{arch}/latest-{arch}，避免互相覆盖
    if [ -z "$PLATFORM_ARG" ] && [ "$NUM" -eq 1 ]; then
        TAGS=(-t "${IMAGE_NAME}:${VERSION}" -t "${IMAGE_NAME}:latest")
    else
        TAGS=(-t "${IMAGE_NAME}:${VERSION}-${arch}" -t "${IMAGE_NAME}:latest-${arch}")
    fi

    docker buildx build \
        --pull=false \
        --platform "linux/$arch" \
        --build-arg VERSION="$VERSION" \
        --build-arg BUILD_VERSION="$BUILD_VERSION" \
        --build-arg BASE_IMAGE="$BASE_IMAGE" \
        --build-arg UV_IMAGE="$UV_IMAGE" \
        "${TAGS[@]}" \
        --load \
        .
done

# 多平台: 推送到 registry 并合并 manifest（可选）
if [ "$NUM" -gt 1 ] && [ -n "$REGISTRY" ]; then
    echo ""
    echo ">>> 推送到 ${REGISTRY} 并合并多平台 manifest..."
    FULL="${REGISTRY}${IMAGE_NAME}"
    for arch in "${PLATFORMS[@]}"; do
        docker tag "${IMAGE_NAME}:${VERSION}-${arch}" "${FULL}:${VERSION}-${arch}"
        docker tag "${IMAGE_NAME}:latest-${arch}" "${FULL}:latest-${arch}"
        docker push "${FULL}:${VERSION}-${arch}"
        docker push "${FULL}:latest-${arch}"
    done
    docker manifest create "${FULL}:${VERSION}" \
        "${FULL}:${VERSION}-${PLATFORMS[0]}" "${FULL}:${VERSION}-${PLATFORMS[1]}"
    docker manifest annotate "${FULL}:${VERSION}" "${FULL}:${VERSION}-${PLATFORMS[0]}" --arch "${PLATFORMS[0]}"
    docker manifest annotate "${FULL}:${VERSION}" "${FULL}:${VERSION}-${PLATFORMS[1]}" --arch "${PLATFORMS[1]}"
    docker manifest create "${FULL}:latest" \
        "${FULL}:latest-${PLATFORMS[0]}" "${FULL}:latest-${PLATFORMS[1]}"
    docker manifest annotate "${FULL}:latest" "${FULL}:latest-${PLATFORMS[0]}" --arch "${PLATFORMS[0]}"
    docker manifest annotate "${FULL}:latest" "${FULL}:latest-${PLATFORMS[1]}" --arch "${PLATFORMS[1]}"
    docker manifest push "${FULL}:${VERSION}"
    docker manifest push "${FULL}:latest"
    echo ">>> 已推送: ${FULL}:${VERSION} (${PLATFORM})"
fi

echo ""
echo "=========================================="
echo "Docker 镜像构建成功!"
echo "=========================================="
echo "镜像标签:"
if [ -z "$PLATFORM_ARG" ] && [ "$NUM" -eq 1 ]; then
    echo "  - ${IMAGE_NAME}:${VERSION}"
    echo "  - ${IMAGE_NAME}:latest"
else
    for arch in "${PLATFORMS[@]}"; do
        echo "  - ${IMAGE_NAME}:${VERSION}-${arch}"
    done
fi
echo "构建版本: $BUILD_VERSION"
echo "=========================================="
echo ""

echo "镜像信息:"
docker images "${IMAGE_NAME}" --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}"
