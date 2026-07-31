#!/usr/bin/env bash
# ======================================================================
# 离线构建准备工作流
# 1. uv lock（连外网）→ 生成标准 lockfile
# 2. 下载所有 wheel 到 packages/（含 amd64 + arm64）
# 3. 重新 uv lock → 本地有的包记录为 registry = "packages"
#
# 用法: ./scripts/build-offline.sh
# 要求: 需要外网连接（PyPI 或加速镜像）
# ======================================================================
set -euo pipefail

cd "$(dirname "$0")/.."

echo "=========================================="
echo "步骤 1/3: 生成标准 lockfile（需外网）"
echo "=========================================="
rm -f uv.lock
uv lock
echo "✓ lockfile 已生成（$(wc -l < uv.lock) 行）"

echo ""
echo "=========================================="
echo "步骤 2/3: 下载依赖 wheel 到 packages/"
echo "=========================================="
mkdir -p packages

# 导出依赖列表（排除 workspace member）
uv export --no-dev --format requirements-txt 2>/dev/null | grep -v "^-e " > /tmp/requirements.txt

# 下载 wheel（多平台）
/root/.local/bin/python3.13 -m pip download \
  --only-binary=:all: --no-deps \
  --platform manylinux_2_17_x86_64 \
  --platform manylinux_2_17_aarch64 \
  --platform manylinux2014_x86_64 \
  --platform manylinux2014_aarch64 \
  --python-version 3.13 \
  --index-url "https://pypi.org/simple" \
  --trusted-host pypi.org \
  --trusted-host files.pythonhosted.org \
  -d packages/ \
  -r /tmp/requirements.txt \
  2>&1 || true

# sdist-only 的包（如 pylatexenc）
/root/.local/bin/python3.13 -m pip download \
  --no-deps \
  --platform manylinux_2_17_x86_64 \
  --python-version 3.13 \
  --index-url "https://pypi.org/simple" \
  --trusted-host pypi.org \
  --trusted-host files.pythonhosted.org \
  -d packages/ \
  -r /tmp/requirements.txt \
  2>&1 || true

echo ""
echo "wheel 统计: $(ls packages/*.whl 2>/dev/null | wc -l) 个"

echo ""
echo "=========================================="
echo "步骤 3/3: 重新生成本地 lockfile"
echo "=========================================="
# 重要: 必须用与 Docker 构建一致的 uv 版本（0.7.13）
# 宿主 uv 版本更新会生成更高 revision 的 lockfile，Docker 内 uv 0.7.13 无法读取
UV_BIN="$(command -v uv || true)"
if [ -n "${UV_BIN:-}" ] && "$UV_BIN" --version 2>/dev/null | grep -q "0.7.13"; then
    echo ">>> 使用宿主 uv 0.7.13"
    LOCK_UV="$UV_BIN"
else
    echo ">>> 从 Docker 镜像 ghcr.io/astral-sh/uv:0.7.13 提取 uv..."
    CONTAINER=$(docker create ghcr.io/astral-sh/uv:0.7.13 2>/dev/null)
    if [ -n "$CONTAINER" ]; then
        mkdir -p /tmp/ocr-uv0713
        docker cp "$CONTAINER:/uv" /tmp/ocr-uv0713/uv 2>/dev/null
        docker rm "$CONTAINER" >/dev/null 2>&1
        chmod +x /tmp/ocr-uv0713/uv
        LOCK_UV=/tmp/ocr-uv0713/uv
    else
        echo "⚠ 无法获取 uv 0.7.13，回退到宿主 uv（注意 lockfile 版本兼容）"
        LOCK_UV="${UV_BIN:-uv}"
    fi
fi
"$LOCK_UV" --version

# 生成临时 pyproject.toml（只有 packages/ 源，没有内网镜像）
# 避免内网镜像的坏包干扰 uv lock 解析
cat > /tmp/pyproject-offline.toml << 'TOMLEOF'
[project]
name = "ocr"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "mineru[core]",
    "fastapi",
    "uvicorn",
    "python-multipart",
    "python-dotenv",
    "latex2mathml>=3.81.0",
    "mathml2omml>=0.0.2",
    "boto3>=1.43.53",
]

[tool.uv.sources]
mineru = { workspace = true }

[tool.uv.workspace]
members = ["MinerU"]

[[tool.uv.index]]
name = "local"
url = "./packages/"
format = "flat"
TOMLEOF

cp pyproject.toml /tmp/pyproject-backup.toml
cp /tmp/pyproject-offline.toml pyproject.toml

rm -f uv.lock
UV_NO_DEFAULT_INDEX=true "$LOCK_UV" lock --find-links packages/ 2>&1 || {
    echo "⚠ 部分包不在 packages/ 中，lockfile 生成可能不完整"
    echo "   缺失的包需要手动下载到 packages/"
}

# 恢复原始 pyproject.toml
cp /tmp/pyproject-backup.toml pyproject.toml

echo ""
echo "lockfile 校验:"
grep -c 'registry = "packages"' uv.lock 2>/dev/null | xargs echo "  本地 packages/ 引用:"
grep -c "pypi.org" uv.lock 2>/dev/null | xargs echo "  残留外网 pypi.org 引用:"

echo ""
echo "=========================================="
echo "离线环境准备完成！"
echo "=========================================="
echo ""
echo "现在可以构建:"
echo "  ./build-docker.sh <VERSION>"
echo ""
echo "多平台构建:"
echo "  ./build-docker.sh <VERSION> amd64,arm64"
echo "  ./scripts/build-multiarch.sh <VERSION>"
