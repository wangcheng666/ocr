#!/usr/bin/env python3
"""从内网 PyPI 镜像批量下载缺失的 aarch64 wheel 到 packages/。

优先走内网源（LAN 快），失败的包记录到 stderr 供人工处理（如 PyPI 直连）。

用法:
    python3 scripts/download_arm64.py          # 下载所有缺失的 aarch64 wheel
    python3 scripts/download_arm64.py torch    # 只下载指定包
"""
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGES_DIR = ROOT / "packages"
PYTHON = "/root/.local/bin/python3.13"
LOCK_FILE = ROOT / "uv.lock"
UV0713 = "/tmp/uv0713"   # 与 Docker 一致的 uv 版本，需先提取（见 build-offline.sh）

# 内网 PyPI 镜像
MIRROR = "http://10.251.166.248:8081/repository/pypi-group/simple"

# aarch64 平台的 pip --platform 参数
AARCH64_PLATFORMS = [
    "manylinux_2_17_aarch64",
    "manylinux2014_aarch64",
    "manylinux_2_28_aarch64",
]

ONLY = sys.argv[1:]  # 可选的包名过滤


def export_requirements() -> list[str]:
    """从 lockfile 导出 core 依赖（精确版本，含传递依赖）。"""
    uv = os.environ.get("UV_BIN", UV0713)
    result = subprocess.run(
        [uv, "export", "--no-dev", "--format", "requirements-txt"],
        capture_output=True, text=True, check=True, cwd=ROOT,
    )
    packages = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-e "):
            continue
        clean = re.sub(r'\s*\\\s*$', '', line)
        if ';' in clean:
            clean = clean.split(';')[0]
        clean = clean.strip()
        if clean and '==' in clean:
            packages.append(clean)
    return packages


def needs_aarch64(pkg_spec: str) -> bool:
    """判断该包是否需要单独的 aarch64 wheel（无 noarch wheel 时需要）。"""
    name = pkg_spec.split("==")[0]
    norm = name.replace("_", "-").lower()
    # 兼容文件名里的下划线和连字符
    existing = [f.name for f in PACKAGES_DIR.iterdir() if f.suffix == ".whl"]
    pat = norm.replace("-", "[_-]")
    rel = [f for f in existing if re.match(rf"^{pat}-", f, re.IGNORECASE)]
    # 已有 noarch wheel → 无需架构专用
    if any('none-any' in f for f in rel):
        return False
    # 已有 aarch64 wheel → 无需再下
    if any('aarch64' in f for f in rel):
        return False
    return True


def download(pkg_spec: str) -> bool:
    """从内网源下载 aarch64 wheel。"""
    args = [PYTHON, "-m", "pip", "download", "--only-binary=:all:", "--no-deps",
            "--python-version", "3.13",
            "--index-url", MIRROR,
            "--trusted-host", "10.251.166.248",
            "-d", str(PACKAGES_DIR)]
    for plat in AARCH64_PLATFORMS:
        args += ["--platform", plat]
    args.append(pkg_spec)
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode == 0:
        return True
    # 失败原因打印（便于排查）
    err = (result.stderr or result.stdout).strip().splitlines()
    print(f"  ✗ {pkg_spec}: {err[-1] if err else 'unknown'}", file=sys.stderr)
    return False


def main():
    reqs = export_requirements()
    print(f"core 依赖共 {len(reqs)} 个")

    todo = [r for r in reqs if needs_aarch64(r)]
    if ONLY:
        todo = [r for r in todo if r.split("==")[0].lower() in [o.lower() for o in ONLY]]
    print(f"需要 aarch64 wheel 的: {len(todo)} 个")

    ok, fail = [], []
    for i, spec in enumerate(todo, 1):
        print(f"[{i}/{len(todo)}] {spec} ...", end=" ", flush=True)
        if download(spec):
            print("✓")
            ok.append(spec)
        else:
            fail.append(spec)

    print("\n==== 结果 ====")
    print(f"成功: {len(ok)}")
    print(f"失败: {len(fail)}")
    for f in fail:
        print(f"  {f}")
    if fail:
        print("\n失败包需从 PyPI 直连下载（如 triton 内网源无 aarch64）:")

    total_arm = len(list(PACKAGES_DIR.glob("*aarch64*.whl")))
    print(f"\npackages/ 现有 aarch64 wheel: {total_arm}")


if __name__ == "__main__":
    main()
