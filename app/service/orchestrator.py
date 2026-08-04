"""编排服务 — 解析 + 存储 + 打包的完整流程（异步）"""

import asyncio
import copy
import os

from loguru import logger

from ..config.settings import MINERU_CUT_IMAGES_DIR
from ..models import HybridOptions
from .engine.core import EngineType, core_parse, parse_hybrid_options
from .output.writers import build_output_file_list, pack_and_upload_zip, write_outputs_to_minio
from .output.render import make_md
from .storage.minio import (
    agenerate_download_url,
    build_async_minio_reader,
    build_async_minio_writer,
    build_minio_reader,
    build_minio_writer,
)
from .output.docx import DocxGenerator
from mineru.utils.enum_class import MakeMode


def _fix_image_paths(obj, prefix: str) -> None:
    """递归遍历 middle_json，给所有 image_path 字段加上目录前缀。"""
    if isinstance(obj, dict):
        for key, val in list(obj.items()):
            if key == "image_path" and isinstance(val, str) and val:
                obj[key] = f"{prefix}/{val}"
            else:
                _fix_image_paths(val, prefix)
    elif isinstance(obj, list):
        for item in obj:
            _fix_image_paths(item, prefix)


async def parse_and_store(
    content: bytes,
    file_name: str,
    engine: EngineType,
    hybrid_opts: HybridOptions,
    output_bucket: str,
    output_prefix: str,
    f_dump_md: bool = True,
    f_dump_content_list: bool = True,
    f_dump_docx: bool = False,
    f_dump_middle_json: bool = True,
    f_dump_model_output: bool = True,
    f_dump_full_page_images: bool = True,
) -> dict:
    """解析文档并将结果写入 MinIO，返回响应数据（异步，事件循环不阻塞）。"""
    stem = ".".join(file_name.split(".")[:-1]) or file_name

    # hybrid/vlm 直接 await MinerU 的 aio_doc_analyze；
    # office 引擎无异步版，内部走 to_thread。
    # image_writer 保持同步（MinerU 异步版内部同步调用 image_writer.write）
    image_writer = build_minio_writer(
        os.path.join(output_prefix, MINERU_CUT_IMAGES_DIR), output_bucket,
    )

    middle_json, model_output, file_type = await core_parse(
        content, file_name, engine, hybrid_opts, image_writer,
    )

    # Markdown 渲染（CPU 密集 → 线程池）
    md_content = await asyncio.to_thread(
        make_md, file_type, middle_json.get("pdf_info", []), MakeMode.MM_MD,
    )

    # ── 深拷贝 middle_json，修正 image_path 用于写入 middle.json ──
    # 引擎只存了文件名（abc.jpg），缺少 cut_images/ 前缀
    # 但 pdf_info 已被 make_md 消费（渲染器会拼接 img_buket_path），
    # 不能直接修改原件，否则 md 中会出现双路径（cut_images/cut_images/abc.jpg）
    middle_json_for_write = copy.deepcopy(middle_json)
    _fix_image_paths(middle_json_for_write, MINERU_CUT_IMAGES_DIR)

    # ── 写入输出文件到 MinIO（异步 writer，await 不阻塞）──────────
    file_writer = build_async_minio_writer(output_prefix, output_bucket)

    docx_gen = None
    if f_dump_docx and file_type in ("pdf", "image"):
        # docx 生成在 to_thread 内执行，可用同步 reader 读裁剪图
        cut_images_reader = build_minio_reader(
            os.path.join(output_prefix, MINERU_CUT_IMAGES_DIR), output_bucket,
        )
        docx_gen = DocxGenerator(img_reader=cut_images_reader, formula_enable=True, table_enable=True)

    await write_outputs_to_minio(
        writer=file_writer,
        stem=stem,
        file_type=file_type,
        middle_json=middle_json_for_write,   # 写 middle.json 用修正后的路径
        model_output=model_output,
        file_info=middle_json.get("pdf_info"),  # 渲染 md/content_list 仍用原件
        cut_images_dir=MINERU_CUT_IMAGES_DIR,
        pdf_bytes=content if file_type == "pdf" else None,
        f_dump_md=f_dump_md,
        f_dump_content_list=f_dump_content_list,
        f_dump_middle_json=f_dump_middle_json,
        f_dump_model_output=f_dump_model_output,
        f_dump_full_page_images=f_dump_full_page_images,
        f_dump_docx=f_dump_docx,
        docx_generator=docx_gen if f_dump_docx else None,
    )

    # ── 打包 ZIP（异步）──────────────────────────────
    files = await build_output_file_list(bucket=output_bucket, prefix=output_prefix)
    zip_name = await pack_and_upload_zip(
        reader=build_async_minio_reader(output_prefix, output_bucket),
        writer=file_writer,
        prefix=output_prefix,
        stem=stem,
        files=files,
    )

    download_url = await agenerate_download_url(
        bucket=output_bucket,
        key=f"{output_prefix}/{zip_name}",
    )

    return {
        "status": "success",
        "message": f"{engine.value} engine parsed {file_name} successfully",
        "content": md_content,
        "engine": engine.value,
        "page_count": len(middle_json.get("pdf_info", [])),
        "download_url": download_url,
    }
