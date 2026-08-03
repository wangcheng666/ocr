"""手动 API 测试脚本 — 测试 /parse 与 /parse/minio 两个接口

覆盖文件类型：
- /parse：pdf(vlm/hybrid)、png(vlm)、docx(office)、pptx(office)、xlsx(office)
- /parse/minio：先通过 boto3 上传 docx/pdf 到 MinIO，再从 MinIO 读取解析

用法：
    cd /root/projects/ocr && .venv/bin/python tests/manual_api_test.py
"""

import json
import os
import sys
import time
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).parents[1]
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(Path(PROJECT_ROOT) / ".env")

import boto3
from botocore.config import Config

BASE_URL = "http://127.0.0.1:8000"

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")
MINIO_BUCKET = os.getenv("MINIO_BUCKET_NAME", "ocr-tmp")

TEST_DATA = PROJECT_ROOT / "tests" / "data"
SAMPLES = {
    "pdf": TEST_DATA / "pdf" / "test_demo.pdf",
    "docx": TEST_DATA / "docx" / "docx_01.docx",
    "pptx": TEST_DATA / "pptx" / "pptx_01.pptx",
    "xlsx": TEST_DATA / "xlsx" / "xlsx_01.xlsx",
    "png": PROJECT_ROOT / "MinerU" / "docs" / "images" / "poly.png",
}

results = []


def record(name, ok, detail=""):
    results.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}" + (f" — {detail}" if detail else ""))


def summarize(r):
    r.raise_for_status()
    data = r.json()
    print(f"      status={data.get('status')} engine={data.get('engine')} "
          f"pages={data.get('page_count')}")
    print(f"      download_url={data.get('download_url')}")
    md = data.get("content") or ""
    print(f"      markdown_preview={md[:120]!r}")
    return data


def test_parse(file_key, engine, extra=None, timeout=900):
    """测试 POST /parse：直接上传文件"""
    fpath = SAMPLES[file_key]
    name = f"/parse {file_key} ({engine})"
    if not fpath.exists():
        record(name, False, f"missing {fpath}")
        return
    files = {"file": (fpath.name, fpath.open("rb"), "application/octet-stream")}
    form = {"engine": engine}
    if extra:
        form.update(extra)
    try:
        t0 = time.time()
        r = requests.post(f"{BASE_URL}/parse", files=files, data=form, timeout=timeout)
        dt = time.time() - t0
        if r.status_code != 200:
            record(name, False, f"HTTP {r.status_code} ({dt:.1f}s): {r.text[:300]}")
            return
        data = summarize(r)
        record(name, True, f"{dt:.1f}s pages={data.get('page_count')}")
    except Exception as e:
        record(name, False, f"exception: {e}")


def upload_to_minio(doc_id, fpath):
    """通过 boto3 上传原始文件到 MinIO（与 /parse 上传同路径结构）"""
    client = boto3.client(
        "s3",
        endpoint_url=f"http://{MINIO_ENDPOINT}",
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )
    key = f"{doc_id}/{fpath.name}"
    client.put_object(Bucket=MINIO_BUCKET, Key=key, Body=fpath.read_bytes())
    return key


def test_parse_minio(file_key, engine, timeout=900):
    """测试 POST /parse/minio：先上传到 MinIO，再从 MinIO 读取解析"""
    fpath = SAMPLES[file_key]
    doc_id = f"manual-test/{file_key}-{int(time.time())}"
    name = f"/parse/minio {file_key} ({engine})"
    if not fpath.exists():
        record(name, False, f"missing {fpath}")
        return
    try:
        key = upload_to_minio(doc_id, fpath)
        print(f"      uploaded -> {MINIO_BUCKET}/{key}")
        form = {
            "doc_id": doc_id,
            "file_name": fpath.name,
            "bucket_name": MINIO_BUCKET,
            "engine": engine,
        }
        t0 = time.time()
        r = requests.post(f"{BASE_URL}/parse/minio", data=form, timeout=timeout)
        dt = time.time() - t0
        if r.status_code != 200:
            record(name, False, f"HTTP {r.status_code} ({dt:.1f}s): {r.text[:300]}")
            return
        data = summarize(r)
        record(name, True, f"{dt:.1f}s pages={data.get('page_count')}")
    except Exception as e:
        record(name, False, f"exception: {e}")


def main():
    print("=" * 70)
    print("1) 健康检查")
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=10)
        record("/health", r.status_code == 200 and r.json() == {"status": "ok"},
               f"HTTP {r.status_code}: {r.json()}")
    except Exception as e:
        record("/health", False, f"exception: {e}")

    print("\n" + "=" * 70)
    print("2) POST /parse — 直接上传解析")
    # office 引擎（docx/pptx/xlsx 原生解析，不依赖 VLM）
    test_parse("docx", "office")
    test_parse("pptx", "office")
    test_parse("xlsx", "office")
    # vlm / hybrid 引擎（PDF / 图片，依赖远程 VLM 服务）
    test_parse("pdf", "vlm")
    test_parse("pdf", "hybrid")
    test_parse("png", "vlm")

    print("\n" + "=" * 70)
    print("3) POST /parse/minio — 从 MinIO 读取解析")
    test_parse_minio("docx", "office")
    test_parse_minio("pptx", "office")
    test_parse_minio("xlsx", "office")
    test_parse_minio("pdf", "vlm")
    test_parse_minio("pdf", "hybrid")
    test_parse_minio("png", "vlm")
    test_parse_minio("png", "hybrid")

    print("\n" + "=" * 70)
    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\n汇总: {passed}/{len(results)} 通过")
    for name, ok, detail in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}  {detail}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
