"""渲染服务 — Markdown、content_list、全页图片等输出格式生成"""

import asyncio
import io
from typing import Any

import pypdfium2 as pdfium
from loguru import logger
from mineru.backend.office.mkcontent.output_builders import union_make as _office_render
from mineru.backend.vlm.vlm_middle_json_mkcontent import union_make as _vlm_render
from mineru.data.data_reader_writer.base import DataWriter
from mineru.utils.enum_class import MakeMode

OFFICE_FILE_TYPES = {"docx", "pptx", "xlsx"}


def _render_content(
    file_type: str,
    pdf_info: list,
    mode: str | MakeMode,
    image_dir: str = "",
) -> str | list:
    """按文件类型选择渲染器。

    docx/pptx/xlsx → Office 渲染器（支持 INDEX、嵌套 LIST）
    pdf/image      → VLM 渲染器  （完整支持 PHONETIC/REF_TEXT/CODE 等）
    """
    if file_type in OFFICE_FILE_TYPES:
        return _office_render(pdf_info, mode, image_dir)
    return _vlm_render(pdf_info, mode, image_dir)


def make_md(
    file_type: str,
    file_info: list,
    mode: str | MakeMode,
    image_dir: str = "",
) -> str:
    """生成 Markdown 文本（兼容所有引擎类型）"""
    result = _render_content(file_type, file_info, mode, image_dir)
    assert isinstance(result, str), f"expected str, got {type(result)}"
    return result


def make_content_list(
    file_type: str,
    file_info: list,
    image_dir: str = "",
) -> list:
    """生成 content_list（兼容所有引擎类型）"""
    result = _render_content(file_type, file_info, MakeMode.CONTENT_LIST, image_dir)
    assert isinstance(result, list), f"expected list, got {type(result)}"
    return result


def _render_full_page_images(
    pdf_bytes: bytes,
    page_count: int | None = None,
) -> list[tuple[str, bytes]]:
    """CPU 密集：将 PDF 每页渲染为 JPG 字节（不落盘，返回 [(filename, bytes)]）。"""
    doc = pdfium.PdfDocument(pdf_bytes)
    if page_count is None:
        page_count = len(doc)

    images: list[tuple[str, bytes]] = []
    for i in range(page_count):
        page = doc[i]
        bitmap = page.render(scale=2)
        pil_img = bitmap.to_pil()
        img_bytes = io.BytesIO()
        pil_img.save(img_bytes, format="JPEG", quality=85)
        img_bytes.seek(0)

        filename = f"full_page/{i}.jpg"
        images.append((filename, img_bytes.getvalue()))
        pil_img.close()

    doc.close()
    return images


async def save_full_page_images(
    pdf_bytes: bytes,
    writer: DataWriter,
    page_count: int | None = None,
) -> list[str]:
    """
    将 PDF 每页渲染为 JPG 并保存到 writer（异步版本）。

    渲染（CPU 密集）在线程池执行，写入（MinIO I/O）用 await 不阻塞事件循环。

    Args:
        pdf_bytes: PDF 文件字节
        writer: AsyncS3DataWriter 等异步 DataWriter
        page_count: 页数，不传则自动获取

    Returns:
        保存的文件名列表 [full_page/0.jpg, full_page/1.jpg, ...]
    """
    images = await asyncio.to_thread(_render_full_page_images, pdf_bytes, page_count)
    for filename, data in images:
        await writer.write(filename, data)

    files = [f for f, _ in images]
    logger.info(f"Saved {len(files)} full-page images")
    return files
