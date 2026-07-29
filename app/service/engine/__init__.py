"""引擎服务 — 文件类型检测、引擎路由、核心解析逻辑"""

from .core import (
    ENGINE_LABELS,
    ENGINE_SUPPORTED_TYPES,
    EngineType,
    classify_file_type,
    core_parse,
    parse_hybrid_options,
    parse_with_engine,
    suggest_engine,
)

__all__ = [
    "EngineType",
    "ENGINE_SUPPORTED_TYPES",
    "ENGINE_LABELS",
    "classify_file_type",
    "suggest_engine",
    "parse_hybrid_options",
    "parse_with_engine",
    "core_parse",
]
