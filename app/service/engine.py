"""引擎服务 — 文件类型检测、引擎路由、核心解析逻辑"""

import json
from enum import Enum
from typing import Any

from fastapi import HTTPException
from loguru import logger

from ..models import HybridOptions
from ..config.settings import VLM_BACKEND, VLM_SERVER_URL


# ── 支持的文件类型 ──────────────────────────────────────
PDF_SUFFIXES = {"pdf"}
IMAGE_SUFFIXES = {"png", "jpeg", "jp2", "webp", "gif", "bmp", "jpg", "tiff"}
DOCX_SUFFIXES = {"docx"}
PPTX_SUFFIXES = {"pptx"}
XLSX_SUFFIXES = {"xlsx"}
OFFICE_SUFFIXES = DOCX_SUFFIXES | PPTX_SUFFIXES | XLSX_SUFFIXES


def classify_file_type(suffix: str) -> str:
    """将文件后缀归类为: pdf, image, docx, pptx, xlsx"""
    if suffix in PDF_SUFFIXES:
        return "pdf"
    if suffix in IMAGE_SUFFIXES:
        return "image"
    if suffix in DOCX_SUFFIXES:
        return "docx"
    if suffix in PPTX_SUFFIXES:
        return "pptx"
    if suffix in XLSX_SUFFIXES:
        return "xlsx"
    return "unknown"


# ── 引擎类型 ─────────────────────────────────────────────
class EngineType(str, Enum):
    """支持的引擎类型"""
    hybrid = "hybrid"
    vlm = "vlm"
    office = "office"


ENGINE_SUPPORTED_TYPES: dict[EngineType, set[str]] = {
    EngineType.hybrid: {"pdf", "image"},
    EngineType.vlm: {"pdf", "image"},
    EngineType.office: {"docx", "pptx", "xlsx"},
}

ENGINE_LABELS: dict[EngineType, str] = {
    EngineType.hybrid: "Hybrid (layout + VLM + OCR)",
    EngineType.vlm: "VLM (纯视觉大模型)",
    EngineType.office: "Office (原生文档解析)",
}


# ── 引擎建议 ─────────────────────────────────────────────
def suggest_engine(file_type: str) -> str:
    if file_type in {"docx", "pptx", "xlsx"}:
        return "office"
    return "hybrid（默认）或 vlm"


# ── Hybrid 扩展参数解析 ─────────────────────────────────
def parse_hybrid_options(raw: str | None) -> HybridOptions:
    """解析 hybrid_options JSON 字符串"""
    if not raw:
        return HybridOptions()
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid hybrid_options JSON: {e}",
        )
    if not isinstance(data, dict):
        raise HTTPException(
            status_code=400,
            detail="hybrid_options must be a JSON object",
        )
    try:
        return HybridOptions(**data)
    except (ValueError, TypeError) as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid hybrid_options field: {e}",
        )


# ── 引擎路由（各引擎的实际调用）─────────────────────────
def _parse_office(content: bytes, file_type: str, image_writer):
    from mineru.backend.office.docx_analyze import office_docx_analyze
    from mineru.backend.office.pptx_analyze import office_pptx_analyze
    from mineru.backend.office.xlsx_analyze import office_xlsx_analyze

    logger.info(f"Using Office engine for {file_type}")
    if file_type == "docx":
        return office_docx_analyze(content, image_writer=image_writer)
    elif file_type == "pptx":
        return office_pptx_analyze(content, image_writer=image_writer)
    else:
        return office_xlsx_analyze(content, image_writer=image_writer)


def _parse_vlm(content: bytes, image_writer):
    from mineru.backend.vlm.vlm_analyze import doc_analyze as vlm_doc_analyze

    logger.info(f"Using VLM engine (backend={VLM_BACKEND}, server_url={VLM_SERVER_URL})")
    middle_json, model_output = vlm_doc_analyze(
        pdf_bytes=content,
        image_writer=image_writer,
        backend=VLM_BACKEND,
        server_url=VLM_SERVER_URL or None,
    )
    return middle_json, model_output


def _parse_hybrid(content: bytes, image_writer, opts: HybridOptions):
    from mineru.backend.hybrid.hybrid_analyze import doc_analyze as hybrid_doc_analyze

    logger.info(
        f"Using Hybrid engine (backend={VLM_BACKEND}, server_url={VLM_SERVER_URL}, "
        f"parse_method={opts.parse_method}, inline_formula={opts.inline_formula_enable}, "
        f"effort={opts.effort})"
    )
    middle_json, model_output = hybrid_doc_analyze(
        pdf_bytes=content,
        image_writer=image_writer,
        backend=VLM_BACKEND,
        server_url=VLM_SERVER_URL or None,
        parse_method=opts.parse_method,
        inline_formula_enable=opts.inline_formula_enable,
        effort=opts.effort,
    )
    return middle_json, model_output


def parse_with_engine(content: bytes, file_type: str, image_writer, hybrid_opts: HybridOptions | None = None):
    """按文件类型路由到对应引擎（供 ocr_router 等外部使用）"""
    if file_type == "docx":
        return _parse_office(content, file_type, image_writer)
    elif file_type == "pptx":
        return _parse_office(content, file_type, image_writer)
    elif file_type == "xlsx":
        return _parse_office(content, file_type, image_writer)
    elif file_type == "vlm":
        return _parse_vlm(content, image_writer)
    else:
        return _parse_hybrid(content, image_writer, hybrid_opts or HybridOptions())


# ── 核心解析流程 ─────────────────────────────────────────
def core_parse(
    content: bytes,
    file_name: str,
    engine: EngineType,
    hybrid_opts: HybridOptions,
    image_writer,
) -> tuple[dict, Any, str]:
    """
    统一的核心解析流程：检测类型 → 校验引擎 → 路由到引擎
    返回 (middle_json, model_output, file_type)
    """
    from mineru.utils.guess_suffix_or_lang import guess_suffix_by_bytes

    file_suffix = guess_suffix_by_bytes(content)
    file_type = classify_file_type(file_suffix)
    logger.info(
        f"Parse: {file_name}, "
        f"detected_type={file_type} (suffix={file_suffix}), "
        f"engine={engine.value}"
    )

    if file_type == "unknown":
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type '{file_suffix}'. "
                f"Supported: PDF, image ({', '.join(sorted(IMAGE_SUFFIXES))}), "
                f"and Office ({', '.join(sorted(OFFICE_SUFFIXES))})"
            ),
        )

    supported = ENGINE_SUPPORTED_TYPES[engine]
    if file_type not in supported:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Engine '{engine.value}' ({ENGINE_LABELS[engine]}) "
                f"does not support '{file_type}' files. "
                f"Supported types: {', '.join(sorted(supported))}. "
                f"Suggested engine: {suggest_engine(file_type)}"
            ),
        )

    if engine == EngineType.office:
        middle_json, model_output = _parse_office(content, file_type, image_writer)
    elif engine == EngineType.vlm:
        middle_json, model_output = _parse_vlm(content, image_writer)
    else:
        middle_json, model_output = _parse_hybrid(content, image_writer, hybrid_opts)

    return middle_json, model_output, file_type
