"""MinIO 存储 — S3DataReader / S3DataWriter 工厂及预签名 URL 生成

提供两套接口：
- 同步（build_minio_reader/writer）：供 MinerU 解析使用。
  MinerU 的 aio_doc_analyze（hybrid/vlm）内部是同步调用 image_writer.write 写裁剪图，
  因此解析阶段必须传同步 writer。
- 异步（build_async_minio_reader/writer / agenerate_download_url）：
  在事件循环中以 await 调用，底层用 asyncio.to_thread 执行同步 boto3，
  不阻塞事件循环。
"""

import asyncio

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
    """构建 MinIO 文件读取器（同步，供线程内使用）"""
    return S3DataReader(
        default_prefix_without_bucket=prefix,
        bucket=bucket_name,
        ak=MINIO_ACCESS_KEY,
        sk=MINIO_SECRET_KEY,
        endpoint_url=f"http://{MINIO_ENDPOINT}",
    )


def build_minio_writer(prefix: str, bucket_name: str) -> S3DataWriter:
    """构建 MinIO 文件写入器（同步，供线程内使用）"""
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


# ── 异步层：await 调用，底层走线程池执行同步 boto3 ──────────
class AsyncS3DataReader:
    """S3DataReader 的异步包装：read / read_at 以 await 调用，不阻塞事件循环。"""

    def __init__(self, reader: S3DataReader):
        self._reader = reader

    @property
    def sync(self) -> S3DataReader:
        """返回底层同步 reader（供 asyncio.to_thread 内使用）"""
        return self._reader

    async def read(self, path: str) -> bytes:
        return await asyncio.to_thread(self._reader.read, path)

    async def read_at(self, path: str, offset: int = 0, limit: int = -1) -> bytes:
        return await asyncio.to_thread(self._reader.read_at, path, offset, limit)

    def __getattr__(self, name):
        # 透传其余属性/方法到底层同步 reader
        return getattr(self._reader, name)


class AsyncS3DataWriter:
    """S3DataWriter 的异步包装：write / write_string 以 await 调用，不阻塞事件循环。"""

    def __init__(self, writer: S3DataWriter):
        self._writer = writer

    @property
    def sync(self) -> S3DataWriter:
        """返回底层同步 writer（供 asyncio.to_thread 内使用）"""
        return self._writer

    async def write(self, path: str, data: bytes) -> None:
        return await asyncio.to_thread(self._writer.write, path, data)

    async def write_string(self, path: str, data: str) -> None:
        return await asyncio.to_thread(self._writer.write_string, path, data)

    def __getattr__(self, name):
        # 透传其余属性/方法到底层同步 writer
        return getattr(self._writer, name)


def build_async_minio_reader(prefix: str, bucket_name: str) -> AsyncS3DataReader:
    """构建异步 MinIO 文件读取器（await 调用，不阻塞事件循环）"""
    return AsyncS3DataReader(build_minio_reader(prefix, bucket_name))


def build_async_minio_writer(prefix: str, bucket_name: str) -> AsyncS3DataWriter:
    """构建异步 MinIO 文件写入器（await 调用，不阻塞事件循环）"""
    return AsyncS3DataWriter(build_minio_writer(prefix, bucket_name))


async def agenerate_download_url(
    bucket: str,
    key: str,
    expires_in: int = 3600,
) -> str:
    """生成 MinIO 对象预签名下载链接（异步，默认 1 小时有效）"""
    client = build_minio_client()
    return await asyncio.to_thread(
        client.generate_presigned_url,
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires_in,
    )


def generate_download_url(
    bucket: str,
    key: str,
    expires_in: int = 3600,
) -> str:
    """生成 MinIO 对象预签名下载链接（同步，兼容旧调用）"""
    client = build_minio_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires_in,
    )
