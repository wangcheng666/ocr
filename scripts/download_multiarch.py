#!/usr/bin/env python3
"""多平台离线 wheel 下载脚本。

从 lockfile 解析依赖，用 pip 从 PyPI 下载 amd64 + arm64 的 wheel 到 packages/。

用法:
    python3 scripts/download_multiarch.py            # amd64 + arm64
    python3 scripts/download_multiarch.py x86_64      # 仅 amd64
    python3 scripts/download_multiarch.py aarch64     # 仅 arm64
"""
import os
import re
import subprocess
import sys
from pathlib import Path

PACKAGES_DIR = Path(__file__).resolve().parent.parent / "packages"
PYTHON = "/root/.local/bin/python3.13"
LOCK_FILE = Path(__file__).resolve().parent.parent / "uv.lock"

# 平台 → (pip --platform 参数)
PLATFORM_MAP = {
    "x86_64": "manylinux_2_17_x86_64",
    "aarch64": "manylinux_2_17_aarch64",
}


def export_requirements() -> list[str]:
    """从 uv.lock 导出扁平依赖列表（含传递依赖，排除 workspace member）。"""
    result = subprocess.run(
        ["uv", "export", "--no-dev", "--format", "requirements-txt"],
        capture_output=True, text=True, check=True,
    )
    packages = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-e "):
            continue
        # 去掉尾部的 \ 和 marker 注释
        clean = re.sub(r'\s*\\\s*$', '', line)
        if ';' in clean:
            clean = clean.split(';')[0]
        clean = clean.strip()
        if clean and '==' in clean:
            packages.append(clean)
    return packages


def download_pkg(pkg_spec: str, platforms: list[str]) -> bool:
    """按平台分别下载单个包的 wheel。"""
    pkg_name = pkg_spec.split("==")[0]
    norm = pkg_name.replace("_", "-").lower()

    # 纯 Python 包（noarch）只需下载一次
    existing = list(PACKAGES_DIR.glob(f"{norm}-*.whl"))
    existing += list(PACKAGES_DIR.glob(f"{pkg_name}-*.whl"))
    if any('none-any' in f.name for f in existing):
        return True

    # 逐平台下载（分开调用，避免一个平台失败导致整体失败）
    ok = True
    for p in platforms:
        tag = 'x86_64' if p.endswith('x86_64') else 'aarch64'
        # 该平台已有则跳过
        if any(tag in f.name for f in existing):
            continue
        args = [PYTHON, "-m", "pip", "download", "--only-binary=:all:", "--no-deps",
                "--python-version", "3.13",
                "--index-url", "https://pypi.org/simple",
                "--trusted-host", "pypi.org",
                "--trusted-host", "files.pythonhosted.org",
                "-d", str(PACKAGES_DIR), "--platform", p,
                pkg_spec]
        result = subprocess.run(args, capture_output=True, text=True)
        if result.returncode != 0:
            ok = False
    if ok:
        print(f"  ✓ {pkg_spec}")
    return ok


def main():
    archs = sys.argv[1:] or ["x86_64", "aarch64"]
    platforms = [PLATFORM_MAP[a] for a in archs if a in PLATFORM_MAP]

    print("=" * 50)
    print("多平台离线 wheel 下载")
    print("=" * 50)
    print(f"目标架构: {', '.join(archs)}")
    print("=" * 50)

    PACKAGES_DIR.mkdir(exist_ok=True)

    packages = export_requirements()
    print(f"共 {len(packages)} 个依赖")

    # 下载所有 wheel
    print("\n>>> 下载 wheel...")
    failed = []
    for pkg in packages:
        if not download_pkg(pkg, platforms):
            failed.append(pkg)

    # 失败的尝试下载 sdist
    if failed:
        print(f"\n>>> {len(failed)} 个包无 wheel，尝试下载 sdist...")
        for pkg in failed:
            pkg_name = pkg.split("==")[0]
            result = subprocess.run(
                [PYTHON, "-m", "pip", "download", "--no-deps",
                 "--index-url", "https://pypi.org/simple",
                 "--trusted-host", "pypi.org",
                 "--trusted-host", "files.pythonhosted.org",
                 "-d", str(PACKAGES_DIR), pkg],
                capture_output=True, text=True,
            )
            if result.returncode == 0:
                print(f"  ✓ {pkg} (sdist)")
            else:
                print(f"  ✗ {pkg}")

    # 统计
    whl_count = len(list(PACKAGES_DIR.glob("*.whl")))
    src_count = len(list(PACKAGES_DIR.glob("*.tar.gz")))
    print(f"\n{'=' * 50}")
    print(f"下载完成!")
    print(f"  wheel: {whl_count} 个")
    print(f"  sdist: {src_count} 个")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    main()
