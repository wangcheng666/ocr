#!/usr/bin/env python3
"""预下载缺失的依赖 wheel 到 packages/ 目录。

用法:
    python3 scripts/download_packages.py

工作流程:
    1. 先从内网 PyPI 镜像下载所有依赖
    2. 内部镜像没有的包，从 PyPI 官方下载
    3. 下载完成后，建议运行 uv lock 重新生成锁文件
"""
import os
import re
import subprocess
import sys
from pathlib import Path

PACKAGES_DIR = Path(__file__).resolve().parent.parent / "packages"
PYTHON = sys.executable
INTERNAL_INDEX = "http://10.251.166.248:8081/repository/pypi-group/simple"
INTERNAL_HOST = "10.251.166.248"


def export_requirements() -> list[str]:
    """从 uv.lock 导出扁平依赖列表（去除 workspace member）。"""
    result = subprocess.run(
        ["uv", "export", "--no-dev", "--format", "requirements-txt"],
        capture_output=True, text=True, check=True,
    )
    packages = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-e "):
            continue
        # 只提取包名和版本，去掉 marker 和尾部的 \
        clean = re.sub(r'\s*\\\s*$', '', line)
        if ';' in clean:
            clean = clean.split(';')[0]
        clean = clean.strip()
        if clean and '==' in clean:
            packages.append(clean)
    return packages


def download(pkg_spec: str, index_url: str, trusted_host: str) -> bool:
    """下载单个包，成功返回 True。"""
    pkg_name = pkg_spec.split("==")[0]
    # 检查是否已存在
    existing = list(PACKAGES_DIR.glob(f"{pkg_name}-*.whl"))
    existing += list(PACKAGES_DIR.glob(f"{pkg_name}-*.tar.gz"))
    if existing:
        print(f"  ✓ {pkg_spec} (已存在)")
        return True

    print(f"  → {pkg_spec} ... ", end="", flush=True)
    result = subprocess.run(
        [PYTHON, "-m", "pip", "download",
         "--only-binary=:all:", "--no-deps",
         "--index-url", index_url,
         "--trusted-host", trusted_host,
         "-d", str(PACKAGES_DIR),
         pkg_spec],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        print("OK")
        return True
    else:
        # 检查是否 sdist-only
        if "Could not find" in result.stderr:
            print("sdist-only (尝试下载源码包)")
            # 尝试不带 --only-binary 下载
            result2 = subprocess.run(
                [PYTHON, "-m", "pip", "download", "--no-deps",
                 "--index-url", index_url,
                 "--trusted-host", trusted_host,
                 "-d", str(PACKAGES_DIR),
                 pkg_spec],
                capture_output=True, text=True,
            )
            if result2.returncode == 0:
                print("  ✓ sdist 下载成功")
                return True
        print(f"失败")
        return False


def main():
    os.chdir(Path(__file__).resolve().parent.parent)
    PACKAGES_DIR.mkdir(exist_ok=True)

    print("=" * 50)
    print("预下载依赖 wheel 到 packages/")
    print("=" * 50)

    packages = export_requirements()
    print(f"共 {len(packages)} 个依赖包")

    # 1. 内部镜像下载
    print("\n>>> 步骤1: 从内部 PyPI 镜像下载...")
    failed = []
    for pkg in packages:
        if not download(pkg, INTERNAL_INDEX, INTERNAL_HOST):
            failed.append(pkg)

    # 2. 缺失的从 PyPI 补充
    if failed:
        print(f"\n>>> 步骤2: 有 {len(failed)} 个包未在内部镜像找到，尝试从 PyPI 下载...")
        for pkg in failed:
            download(pkg, "https://pypi.org/simple", "pypi.org")

    # 统计
    whl_count = len(list(PACKAGES_DIR.glob("*.whl")))
    src_count = len(list(PACKAGES_DIR.glob("*.tar.gz")))
    print(f"\n{'=' * 50}")
    print(f"完成! packages/ 目录: {whl_count} 个 wheel, {src_count} 个源码包")
    print(f"{'=' * 50}")
    print()
    print("建议后续步骤:")
    print("  1. 运行 uv lock 重新生成锁文件（使包来源指向本地/内部）")
    print("  2. 运行 ./build.sh <VERSION> 构建 Docker 镜像")


if __name__ == "__main__":
    main()
