"""MinIO 存储 — S3DataReader / S3DataWriter 工厂及预签名 URL 生成"""

import boto3
from botocore.config import Config
from mineru.data.data_reader_writer.s3 import S3DataReader, S3DataWriter

from ...config.settings import (
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


def build_minio_client():
    """构建低级别 boto3 S3 客户端，用于 presigned URL 等操作"""
    return boto3.client(
        "s3",
        endpoint_url=f"http://{MINIO_ENDPOINT}",
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def generate_download_url(
    bucket: str,
    key: str,
    expires_in: int = 3600,
) -> str:
    """生成 MinIO 对象预签名下载链接（默认 1 小时有效）"""
    client = build_minio_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires_in,
    )
