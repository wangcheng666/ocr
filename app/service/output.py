"""输出服务 — 解析结果的后处理（写 MinIO、生成文件等）"""

import io
import json
import zipfile
from typing import Any

import pypdfium2 as pdfium
from loguru import logger
from mineru.backend.office.mkcontent.output_builders import \
    union_make as _office_render
from mineru.backend.vlm.vlm_middle_json_mkcontent import \
    union_make as _vlm_render
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


def save_full_page_images(
    pdf_bytes: bytes,
    writer: DataWriter,
    page_count: int | None = None,
) -> list[str]:
    """
    将 PDF 每页渲染为 JPG 并保存到 writer

    Args:
        pdf_bytes: PDF 文件字节
        writer: DataWriter（本地或 MinIO）
        page_count: 页数，不传则自动获取

    Returns:
        保存的文件名列表 [full_page/0.jpg, full_page/1.jpg, ...]
    """
    doc = pdfium.PdfDocument(pdf_bytes)
    if page_count is None:
        page_count = len(doc)

    files = []
    for i in range(page_count):
        page = doc[i]
        bitmap = page.render(scale=2)  # 2x 缩放以保持清晰度
        pil_img = bitmap.to_pil()
        img_bytes = io.BytesIO()
        pil_img.save(img_bytes, format="JPEG", quality=85)
        img_bytes.seek(0)

        filename = f"full_page/{i}.jpg"
        writer.write(filename, img_bytes.getvalue())
        files.append(filename)
        pil_img.close()

    doc.close()
    logger.info(f"Saved {len(files)} full-page images")
    return files


def write_outputs_to_minio(
    *,
    writer: DataWriter,
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
    f_dump_full_page_images: bool = False,
    f_make_md_mode: str | MakeMode = MakeMode.MM_MD,
):
    """
    将解析结果写入 MinIO

    Args:
        writer: 输出目录的 DataWriter
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
        md_content = make_md(file_type, file_info, f_make_md_mode, cut_images_dir)
        writer.write_string(f"{stem}.md", md_content)

    if f_dump_content_list and file_info is not None:
        content_list = make_content_list(file_type, file_info, cut_images_dir)
        writer.write_string(
            f"{stem}_content_list.json",
            json.dumps(content_list, ensure_ascii=False, indent=4),
        )

    if f_dump_middle_json and middle_json:
        writer.write_string(
            f"{stem}_middle.json",
            json.dumps(middle_json, ensure_ascii=False, indent=4),
        )

    if f_dump_model_output and model_output is not None:
        writer.write_string(
            f"{stem}_model.json",
            json.dumps(model_output, ensure_ascii=False, indent=4),
        )

    if f_dump_full_page_images and pdf_bytes is not None:
        save_full_page_images(pdf_bytes, writer)

    logger.info(f"Output files written to MinIO: {stem}")


def build_output_file_list(
    bucket: str,
    prefix: str,
) -> list[str]:
    """递归扫描 MinIO 路径下所有文件，返回相对路径列表（供 ZIP 打包使用）"""
    from ..service.storage import build_minio_client

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


def pack_and_upload_zip(
    *,
    reader,
    writer: DataWriter,
    prefix: str,
    stem: str,
    files: list[str],
    zip_name: str | None = None,
) -> str:
    """
    从 MinIO 读取输出文件，打包 ZIP 并上传

    Args:
        reader: S3DataReader（需与 writer 同 bucket/prefix）
        writer: S3DataWriter
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
        existing = reader.read(zip_name)
        if existing:
            logger.info(f"ZIP already exists: {prefix}/{zip_name}, skipping")
            return zip_name
    except Exception:
        pass

    # 从 MinIO 读取所有文件，打包 ZIP
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            try:
                data = reader.read(f)
                if data:
                    zf.writestr(f, data)
                    logger.debug(f"Added to ZIP: {f} ({len(data)} bytes)")
            except Exception as e:
                logger.warning(f"Failed to read {f} for ZIP: {e}")

    buf.seek(0)
    writer.write(zip_name, buf.getvalue())
    logger.info(f"ZIP uploaded: {prefix}/{zip_name} ({buf.tell()} bytes)")

    return zip_name
