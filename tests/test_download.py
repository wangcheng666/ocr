"""测试解析 + 直接从 MinIO 下载 middle.json 和 .md 到 tests/results/pdf/"""
import json
import os
import re
import sys

import boto3
import requests

# ── 配置 ──────────────────────────────────────────────
API_URL = "http://localhost:8000/parse"
MINIO_ENDPOINT = "10.251.146.131:9000"
MINIO_ACCESS_KEY = "minioadmin"
MINIO_SECRET_KEY = "minioadmin"
MINIO_BUCKET = "ocr-tmp"
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results", "pdf")

session = requests.Session()
session.trust_env = False

# ── 1. 解析 ──────────────────────────────────────────
pdf_path = os.path.join(os.path.dirname(__file__), "data", "pdf", "图表测试文件.pdf")
with open(pdf_path, "rb") as f:
    resp = session.post(
        API_URL,
        files={"file": f},
        data={"engine": "vlm"},
        timeout=300,
    )
data = resp.json()
assert data.get("status") == "success", f"Parse failed: {data}"
print(f"✅ Parse success: {data.get('page_count')} pages")

# ── 2. 从 download_url 提取 output_prefix ─────────────
download_url = data["download_url"]
# URL 格式: http://10.251.146.131:9000/ocr-tmp/{uuid}/图表测试文件.zip?...
m = re.search(r"/ocr-tmp/([^/]+)/", download_url)
assert m, f"Cannot extract prefix from URL: {download_url}"
prefix = m.group(1)
print(f"📁 Output prefix: {prefix}")

# ── 3. 直接从 MinIO 下载文件 ──────────────────────────
s3 = boto3.client(
    "s3",
    endpoint_url=f"http://{MINIO_ENDPOINT}",
    aws_access_key_id=MINIO_ACCESS_KEY,
    aws_secret_access_key=MINIO_SECRET_KEY,
    config=boto3.session.Config(signature_version="s3v4"),
    region_name="us-east-1",
)

stem = "图表测试文件"
files_to_get = [
    f"{stem}.md",
    f"{stem}_middle.json",
]

os.makedirs(RESULTS_DIR, exist_ok=True)

for filename in files_to_get:
    key = f"{prefix}/{filename}"
    local_path = os.path.join(RESULTS_DIR, filename)
    try:
        obj = s3.get_object(Bucket=MINIO_BUCKET, Key=key)
        content = obj["Body"].read()
        with open(local_path, "wb") as f:
            f.write(content)
        size_kb = len(content) / 1024
        print(f"✅ Downloaded {filename} ({size_kb:.1f} KB) → {local_path}")
    except Exception as e:
        print(f"❌ Failed to download {key}: {e}")

# ── 4. 验证 middle.json 中 image_path 是否已修正 ──────
mj_path = os.path.join(RESULTS_DIR, f"{stem}_middle.json")
if os.path.exists(mj_path):
    with open(mj_path) as f:
        mj = json.load(f)

    found = []

    def walk(obj):
        if isinstance(obj, dict):
            if "image_path" in obj and obj["image_path"]:
                found.append(obj["image_path"])
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(mj)
    print(f"\n🔍 image_path entries ({len(found)}):")
    for p in found:
        print(f"   {p}")

    all_ok = all(p.startswith("cut_images/") for p in found)
    print(f"\n{'✅' if all_ok else '❌'} All have cut_images/ prefix: {all_ok}")
