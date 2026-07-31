#!/usr/bin/env bash
# ======================================================================
# 从内网 PyPI 镜像下载所有需要的 wheel 到 packages/
# 用法: bash scripts/download-all.sh
# ======================================================================
set -euo pipefail
cd "$(dirname "$0")/.."
MIRROR="http://10.251.166.248:8081/repository/pypi-group/packages"

echo "=========================================="
echo "从内网镜像批量下载 wheel 到 packages/"
echo "=========================================="

# 从 uv.lock 提取所有 wheel 文件名
grep -oP 'https://files\.pythonhosted\.org/packages/[^"]+\.whl' uv.lock | sort -u > /tmp/all_wheels.txt
total=$(wc -l < /tmp/all_wheels.txt)
echo "共 $total 个 wheel"

# 对每个 wheel，从内网镜像下载
count=0
success=0
while IFS= read -r url; do
    filename=$(basename "$url")
    # 从文件名解析包名和版本 (name-version-platform.whl)
    # 提取第一个 - 之前的部分作为包名
    pkg_name=$(echo "$filename" | sed -E 's/^([a-z0-9_.-]+?)-[0-9].*$/\1/' | tr '[:upper:]' '[:lower:]')
    # 提取版本号 (第一个数字段开始到平台标记前)
    pkg_ver=$(echo "$filename" | grep -oP '(?<=^[a-z0-9_.-]+?)-(\d+\.\d+\.\d+[^-]*)' | sed 's/^-//')
    
    # 跳过无法解析的
    [ -z "$pkg_ver" ] && { count=$((count+1)); continue; }
    
    # 检查是否已存在
    [ -f "packages/$filename" ] && { count=$((count+1)); continue; }
    
    mirror_url="$MIRROR/$pkg_name/$pkg_ver/$filename"
    echo "[$((count+1))/$total] $pkg_name==$pkg_ver ... " | tr -d '\n'
    
    if curl -sf "$mirror_url" -o "packages/$filename" --connect-timeout 10 --max-time 120 2>/dev/null; then
        echo "OK"
        success=$((success+1))
    else
        echo "未找到(404)"
    fi
    count=$((count+1))
done < /tmp/all_wheels.txt

echo ""
echo "=========================================="
echo "完成! 从内网镜像下载了 $success 个新 wheel"
echo "packages/ 目录共 $(ls packages/*.whl 2>/dev/null | wc -l) 个文件"
echo "=========================================="
echo ""
echo "剩余未下载的包需从 PyPI 手动下载:"
