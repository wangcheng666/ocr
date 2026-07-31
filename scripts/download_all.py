#!/usr/bin/env python3
"""从内网 PyPI 镜像批量下载 wheel 到 packages/。

用法:
    python3 scripts/download_all.py

从 uv.lock 提取所有 wheel URL，映射到内网镜像地址并下载。
"""
import re
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

MIRROR = "http://10.251.166.248:8081/repository/pypi-group/packages"
PACKAGES_DIR = Path(__file__).resolve().parent.parent / "packages"
LOCK_FILE = Path(__file__).resolve().parent.parent / "uv.lock"


def parse_wheel_filename(filename: str):
    """从 wheel 文件名解析包名和版本。"""
    # 处理有平台标记的: name-version-platform.whl
    # 例如: accelerate-1.14.0-py3-none-any.whl
    # 例如: torch-2.8.0-cp313-cp313-manylinux_2_28_x86_64.whl
    m = re.match(r'^(.+?)-(\d+\.\d+[\d.]*[a-z0-9]*?)-(.*)\.whl$', filename)
    if m:
        name = m.group(1).lower()
        version = m.group(2)
        return name, version
    return None, None


def download_from_mirror(filename: str) -> bool:
    """从内网镜像下载 wheel，成功返回 True。"""
    dest = PACKAGES_DIR / filename
    if dest.exists():
        return True

    name, version = parse_wheel_filename(filename)
    if not name or not version:
        return False

    url = f"{MIRROR}/{name}/{version}/{filename}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=120) as resp:
            if resp.status == 200:
                with open(dest, 'wb') as f:
                    f.write(resp.read())
                return True
    except (urllib.error.HTTPError, urllib.error.URLError, OSError):
        pass
    return False


def main():
    PACKAGES_DIR.mkdir(exist_ok=True)

    with open(LOCK_FILE) as f:
        content = f.read()

    # 提取所有 wheel URL，只取 cp313 和 noarch 的（Linux x86_64 或纯 Python）
    all_urls = re.findall(r'https://files\.pythonhosted\.org/packages/[^"\' ]+\.whl', content)
    
    # 过滤：只保留 Linux x86_64 或纯 Python 的 wheel
    # 匹配模式:
    #   - cp313 + manylinux + x86_64
    #   - cp310-abi3 / cp38-abi3 + manylinux + x86_64 (稳定 ABI)
    #   - py3-none-any / py2.py3-none-any (纯 Python)
    #   - py3-none-manylinux (如 nvidia 包)
    #   - cp39-abi3 + manylinux + x86_64
    filtered = []
    for url in all_urls:
        fname = url.rsplit("/", 1)[-1]
        # Linux x86_64 条件
        is_linux_x64 = ('manylinux' in fname and 'x86_64' in fname) or 'manylinux2014' in fname
        # Python 版本条件
        is_cp313 = 'cp313' in fname
        is_abi3 = 'abi3' in fname
        is_noarch = fname.endswith('-py3-none-any.whl') or fname.endswith('-py2.py3-none-any.whl')
        is_nopy = 'py3-none' in fname and 'manylinux' in fname  # nvidia-* 等
        
        if (is_linux_x64 and (is_cp313 or is_abi3)) or is_noarch or (is_nopy and is_linux_x64):
            filtered.append(url)
    
    urls = sorted(set(filtered))

    print(f"从 uv.lock 中找到 {len(urls)} 个 wheel")

    already = len(list(PACKAGES_DIR.glob("*.whl")))
    print(f"packages/ 已有 {already} 个")

    success = 0
    failed = []
    for i, url in enumerate(urls, 1):
        filename = url.rsplit("/", 1)[-1]
        if (PACKAGES_DIR / filename).exists():
            continue

        print(f"  [{i}/{len(urls)}] {filename[:50]}... ", end="", flush=True)
        if download_from_mirror(filename):
            print("OK")
            success += 1
        else:
            print("未找到")
            failed.append(filename)

    total = len(list(PACKAGES_DIR.glob("*.whl")))
    print(f"\n完成! 新下载 {success} 个, packages/ 共 {total} 个 wheel")
    if failed:
        print(f"\n以下 {len(failed)} 个包内网镜像没有，需从 PyPI 手动下载:")
        for f in failed:
            print(f"  {f}")


if __name__ == "__main__":
    main()
