"""存储服务 — MinIO S3DataReader / S3DataWriter 工厂"""

from .minio import (
    build_minio_client,
    build_minio_reader,
    build_minio_writer,
    check_minio_configured,
    generate_download_url,
)

__all__ = [
    "check_minio_configured",
    "build_minio_reader",
    "build_minio_writer",
    "build_minio_client",
    "generate_download_url",
]
