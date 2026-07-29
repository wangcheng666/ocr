"""应用配置 — 所有环境变量在此统一读取"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parents[2] / ".env")

# MinerU 配置文件（mineru.json）
os.environ.setdefault(
    "MINERU_TOOLS_CONFIG_JSON",
    str(Path(__file__).parents[2] / "app" / "configs" / "mineru.json"),
)

# ── VLM 推理后端 ────────────────────────────────────────
VLM_BACKEND = os.getenv("VLM_BACKEND", "http-client")
VLM_SERVER_URL = os.getenv("VLM_SERVER_URL", "")

# ── MinIO ────────────────────────────────────────────────
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "")
MINIO_BUCKET_NAME = os.getenv("MINIO_BUCKET_NAME", "")
MINERU_CUT_IMAGES_DIR = os.getenv("MINERU_CUT_IMAGES_DIR", "cut_images")
