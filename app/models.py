"""OCR 解析接口请求模型"""

from typing import Optional

from pydantic import BaseModel, Field


class HybridOptions(BaseModel):
    """Hybrid 引擎专属参数"""
    parse_method: str = Field("auto", description="解析方式：auto（自动判断）或 ocr（强制 OCR 模式）")
    inline_formula_enable: bool = Field(True, description="是否启用行内公式识别")
    effort: str = Field("medium", description="解析强度：medium 或 high")


class OCRParseWithMinioRequest(BaseModel):
    """兼容原 `/ocr_parse/async_parse` 接口的请求体"""
    doc_id: str = Field(..., description="文档 ID，用作 MinIO 路径前缀")
    file_name: str = Field(..., description="MinIO 中的文件名")
    bucket_name: Optional[str] = Field(None, description="MinIO 存储桶，不传则使用默认桶")

    f_dump_image_list: bool = Field(True, description="是否导出图片列表")
    f_draw_layout_bbox: bool = Field(True, description="是否绘制 layout bbox")
    f_dump_md: bool = Field(True, description="是否导出 Markdown")
    f_dump_middle_json: bool = Field(True, description="是否导出 middle_json")
    f_dump_model_output: bool = Field(True, description="是否导出模型输出")
    f_dump_content_list: bool = Field(True, description="是否导出 content_list")
    f_dump_docx: bool = Field(True, description="是否导出 docx")
    f_make_md_mode: str = Field("auto", description="Markdown 生成模式")

    hybrid: Optional[HybridOptions] = Field(None, description="Hybrid 引擎专属参数")
