"""存储服务 — MinIO S3DataReader / S3DataWriter 工厂"""

from mineru.data.data_reader_writer.s3 import S3DataReader, S3DataWriter

from ..config.settings import (
    MINIO_ENDPOINT,
    MINIO_ACCESS_KEY,
    MINIO_SECRET_KEY,
)


def check_minio_configured():
    """检查 MinIO 环境变量是否配置完整，否则抛出 500"""
    if not all([MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY]):
        raise RuntimeError(
            "MinIO not configured. Set MINIO_ENDPOINT, MINIO_ACCESS_KEY, "
            "MINIO_SECRET_KEY in .env"
        )


def build_minio_reader(prefix: str, bucket_name: str) -> S3DataReader:
    """构建 MinIO 文件读取器"""
    return S3DataReader(
        default_prefix_without_bucket=prefix,
        bucket=bucket_name,
        ak=MINIO_ACCESS_KEY,
        sk=MINIO_SECRET_KEY,
        endpoint_url=f"http://{MINIO_ENDPOINT}",
    )


def build_minio_writer(prefix: str, bucket_name: str) -> S3DataWriter:
    """构建 MinIO 文件写入器"""
    return S3DataWriter(
        default_prefix_without_bucket=prefix,
        bucket=bucket_name,
        ak=MINIO_ACCESS_KEY,
        sk=MINIO_SECRET_KEY,
        endpoint_url=f"http://{MINIO_ENDPOINT}",
    )
