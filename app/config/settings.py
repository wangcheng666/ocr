"""应用配置 — 所有环境变量在此统一读取"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parents[2] / ".env")

# MinerU 配置文件（mineru.json）路径由 .env 的 MINERU_TOOLS_CONFIG_JSON 提供，
# 用 ${PWD} 插值展开为工作目录绝对路径（本地=项目根，Docker=/app）。
# 注意：MinerU 会把纯相对路径拼到 ~/ 下（get_tools_config_file_path），故不能用纯相对路径。

# ── VLM 推理后端 ────────────────────────────────────────
VLM_BACKEND = os.getenv("VLM_BACKEND", "http-client")
VLM_SERVER_URL = os.getenv("VLM_SERVER_URL", "")

# ── MinIO ────────────────────────────────────────────────
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "")
MINIO_BUCKET_NAME = os.getenv("MINIO_BUCKET_NAME", "")
MINERU_CUT_IMAGES_DIR = os.getenv("MINERU_CUT_IMAGES_DIR", "cut_images")
