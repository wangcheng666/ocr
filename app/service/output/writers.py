"""打包服务 — 将解析结果写入 MinIO 并打包为 ZIP（异步版本）"""

import asyncio
import io
import json
import zipfile
from typing import Any

from loguru import logger
from mineru.utils.enum_class import MakeMode

from .render import make_content_list, make_md, save_full_page_images
from ..storage.minio import build_minio_client


async def write_outputs_to_minio(
    *,
    writer: Any,   # AsyncS3DataWriter
    stem: str,
    file_type: str,
    middle_json: dict[str, Any] | None = None,
    model_output: list | Any | None = None,
    file_info: list | None = None,
    cut_images_dir: str = "",
    pdf_bytes: bytes | None = None,
    f_dump_md: bool = False,
    f_dump_content_list: bool = False,
    f_dump_middle_json: bool = True,
    f_dump_model_output: bool = True,
    f_dump_docx: bool = False,
    f_dump_full_page_images: bool = False,
    f_make_md_mode: str | MakeMode = MakeMode.MM_MD,
    docx_generator: Any | None = None,
):
    """
    将解析结果写入 MinIO（异步）。

    CPU 密集的渲染（md/content_list/docx/全页图）在线程池执行，
    MinIO 写入用 await 调用异步 writer，不阻塞事件循环。

    Args:
        writer: 异步输出目录的 DataWriter（AsyncS3DataWriter）
        stem: 输出文件名（不含后缀）
        file_type: 文件类型（pdf/image/docx/pptx/xlsx）
        middle_json: 完整的 middle_json
        model_output: 模型原始输出
        file_info: middle_json["pdf_info"]
        cut_images_dir: 图片子目录
        pdf_bytes: PDF 文件字节（传入后配合 f_dump_full_page_images 使用）
        f_dump_md: 是否生成 Markdown
        f_dump_content_list: 是否生成 content_list JSON
        f_dump_middle_json: 是否写入 middle.json
        f_dump_model_output: 是否写入 model.json
        f_dump_full_page_images: 是否保存每页全页图片（需传入 pdf_bytes）
        f_make_md_mode: Markdown 生成模式
    """
    if f_dump_md and file_info is not None:
        md_content = await asyncio.to_thread(
            make_md, file_type, file_info, f_make_md_mode, cut_images_dir
        )
        await writer.write_string(f"{stem}.md", md_content)

    if f_dump_content_list and file_info is not None:
        content_list = await asyncio.to_thread(
            make_content_list, file_type, file_info, cut_images_dir
        )
        await writer.write_string(
            f"{stem}_content_list.json",
            json.dumps(content_list, ensure_ascii=False, indent=4),
        )

    if f_dump_middle_json and middle_json:
        await writer.write_string(
            f"{stem}_middle.json",
            json.dumps(middle_json, ensure_ascii=False, indent=4),
        )

    if f_dump_model_output and model_output is not None:
        await writer.write_string(
            f"{stem}_model.json",
            json.dumps(model_output, ensure_ascii=False, indent=4),
        )

    if f_dump_full_page_images and pdf_bytes is not None:
        await save_full_page_images(pdf_bytes, writer)

    if f_dump_docx and file_type in ("pdf", "image") and file_info is not None and docx_generator is not None:
        try:
            # docx 双写：标准版（公式渲染为 OMML）+ 原始公式版（LaTeX 原文）。
            # CPU 密集 + 内部读图（同步 I/O），整体放线程池
            def _gen() -> list[tuple[str, bytes]]:
                docs = [
                    ("", docx_generator.generate(file_info)),
                    ("_with_raw_formula", docx_generator.generate_with_raw_formula(file_info)),
                ]
                out: list[tuple[str, bytes]] = []
                for suffix, doc in docs:
                    buf = io.BytesIO()
                    doc.save(buf)
                    out.append((suffix, buf.getvalue()))
                return out

            for suffix, data in await asyncio.to_thread(_gen):
                await writer.write(f"{stem}{suffix}.docx", data)
        except Exception as e:
            logger.error(f"docx 生成失败: {e}")

    logger.info(f"Output files written to MinIO: {stem}")


async def build_output_file_list(
    bucket: str,
    prefix: str,
) -> list[str]:
    """递归扫描 MinIO 路径下所有文件，返回相对路径列表（供 ZIP 打包使用，异步）"""
    def _scan() -> list[str]:
        client = build_minio_client()
        keys: list[str] = []
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                rel = key.removeprefix(prefix).removeprefix("/")
                if rel:
                    keys.append(rel)
        keys.sort()
        return keys

    return await asyncio.to_thread(_scan)


async def pack_and_upload_zip(
    *,
    reader: Any,    # AsyncS3DataReader
    writer: Any,    # AsyncS3DataWriter
    prefix: str,
    stem: str,
    files: list[str],
    zip_name: str | None = None,
) -> str:
    """
    从 MinIO 读取输出文件，打包 ZIP 并上传（异步）。

    文件读取用 await 并发执行；ZIP 压缩（CPU 密集）在线程池执行。

    Args:
        reader: 异步 S3DataReader（需与 writer 同 bucket/prefix）
        writer: 异步 S3DataWriter
        prefix: MinIO 路径前缀
        stem: 文件名主干
        files: 要打包的文件名列表（如 ["doc.md", "doc_middle.json"]）
        zip_name: ZIP 文件名，默认 {stem}.zip

    Returns:
        上传后的 ZIP 文件名
    """
    zip_name = zip_name or f"{stem}.zip"

    # 检查 ZIP 是否已存在
    try:
        existing = await reader.read(zip_name)
        if existing:
            logger.info(f"ZIP already exists: {prefix}/{zip_name}, skipping")
            return zip_name
    except Exception:
        pass

    # 并发从 MinIO 读取所有文件
    async def _read_one(f: str) -> tuple[str, bytes | None]:
        try:
            return f, await reader.read(f)
        except Exception as e:
            logger.warning(f"Failed to read {f} for ZIP: {e}")
            return f, None

    items: list[tuple[str, bytes | None]] = await asyncio.gather(
        *[_read_one(f) for f in files]
    )

    # CPU 密集：压缩打包（线程池）
    def _zip() -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for f, data in items:
                if data:
                    zf.writestr(f, data)
                    logger.debug(f"Added to ZIP: {f} ({len(data)} bytes)")
        return buf.getvalue()

    data = await asyncio.to_thread(_zip)
    await writer.write(zip_name, data)
    logger.info(f"ZIP uploaded: {prefix}/{zip_name} ({len(data)} bytes)")

    return zip_name
