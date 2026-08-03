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
#   - 基础镜像选择在 Dockerfile 内部（--build-arg TARGETARCH=amd64|arm64）
#   - 单平台: 打 {VERSION} + latest 标签
#   - 多平台: 各架构打 {VERSION}-{arch} 标签（仅本地构建，不推送 registry）
# ======================================================================
set -euo pipefail

cd "$(dirname "$0")"

IMAGE_NAME="${IMAGE_NAME:-ocr-server}"
VERSION="${1:?"错误: 请提供 VERSION 参数\n用法: $0 <VERSION> [PLATFORM]\n示例: $0 v1.0.0"}"
PLATFORM_ARG="${2:-}"
PLATFORM="${PLATFORM_ARG:-}"
BUILD_VERSION=$(date +"%Y%m%d%H%M%S")

# 默认平台 = 当前机器架构（未显式指定时打 {VERSION}/latest 标签）
if [ -z "$PLATFORM" ]; then
    case "$(uname -m)" in
        x86_64|amd64) PLATFORM="amd64" ;;
        aarch64|arm64) PLATFORM="arm64" ;;
        *) echo "错误: 未知架构 $(uname -m)"; exit 1 ;;
    esac
fi

# 校验架构（基础镜像选择逻辑已在 Dockerfile 内部，脚本只需传 TARGETARCH）
allowed_arch() {
    case "$1" in
        amd64|arm64) return 0 ;;
        *) return 1 ;;
    esac
}

echo "=========================================="
echo "开始构建 Docker 镜像"
echo "=========================================="
echo "VERSION:       $VERSION"
echo "BUILD_VERSION: $BUILD_VERSION"
echo "IMAGE_NAME:    $IMAGE_NAME"
echo "PLATFORM:      $PLATFORM"
echo "=========================================="

# 解析平台列表
IFS=',' read -ra PLATFORMS <<< "$PLATFORM"
NUM=${#PLATFORMS[@]}

# 每个平台单独构建（各自的基础镜像不同，无法用单次 --platform a,b）
for arch in "${PLATFORMS[@]}"; do
    if ! allowed_arch "$arch"; then
        echo "错误: 不支持的平台 '$arch'（可选: amd64, arm64）"
        exit 1
    fi

    echo ""
    echo ">>> 构建 $arch ..."
    echo "    TARGETARCH: $arch（基础镜像由 Dockerfile 内部选择）"

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
        --build-arg TARGETARCH="$arch" \
        "${TAGS[@]}" \
        --load \
        .
done

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
