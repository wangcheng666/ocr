"""MinerU Custom API Server — Controller"""
import uuid
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv(Path(__file__).parents[2] / ".env")

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import BaseModel

from ..config.settings import MINIO_BUCKET_NAME
from ..service.engine.core import EngineType, parse_hybrid_options
from ..service.orchestrator import parse_and_store
from ..service.storage.minio import build_async_minio_reader, build_async_minio_writer


# ── FastAPI 应用 ─────────────────────────────────────────
app = FastAPI(
    title="MinerU Document Parse API",
    description="""文档解析服务，支持 PDF / 图片 / Office 文件。

**返回的 ZIP 包包含：**
- `{stem}.md` — Markdown 渲染结果
- `{stem}_content_list.json` — 结构化 content_list
- `{stem}_middle.json` — 中间结果（含 pdf_info）
- `{stem}_model.json` — 模型原始输出
- `{stem}.docx` — [可选] 生成的 Word 文档（仅 PDF，需 f_dump_docx=true）
- `cut_images/` — 解析过程中裁剪的图片
""",
    version="1.0.0",
)


@app.get("/health", summary="健康检查", description="返回服务运行状态。")
async def health():
    return {"status": "ok"}


@app.post(
    "/parse",
    summary="上传文档解析",
    description="""上传文件并解析，结果写入 MinIO，返回 ZIP 下载链接。

**支持的引擎：**
- `vlm` — 纯视觉大模型（默认，支持 PDF / 图片）
- `hybrid` — 布局分析 + VLM + OCR（支持 PDF / 图片）
- `office` — 原生 Office 解析（支持 docx / pptx / xlsx）

**输出控制参数：**
所有 `f_dump_*` 参数控制是否生成对应文件。默认生成的：middle.json、model.json。
Markdown 和 content_list 默认生成。
""",
    response_description="""解析结果，含 markdown 正文、引擎信息、页数、ZIP 下载链接""",
)
async def parse_document(
    file: UploadFile = File(..., description="待解析的文件（PDF / 图片 / docx / pptx / xlsx）"),
    engine: EngineType = Form(EngineType.vlm, description="解析引擎：vlm（默认）/ hybrid / office"),
    hybrid_options: Optional[str] = Form(None, description="hybrid 引擎的 VLM 配置参数（JSON 字符串）"),
    f_dump_md: bool = Form(True, description="是否生成 Markdown"),
    f_dump_content_list: bool = Form(True, description="是否生成 content_list JSON"),
    f_dump_middle_json: bool = Form(True, description="是否写入 middle.json"),
    f_dump_model_output: bool = Form(True, description="是否写入 model.json（原始模型输出）"),
    f_dump_full_page_images: bool = Form(True, description="是否保存 PDF 每页全页图片"),
    f_dump_docx: bool = Form(False, description="[仅 PDF] 是否生成 Word 文档（.docx）"),
):
    hybrid_opts = parse_hybrid_options(hybrid_options)
    content = await file.read()
    file_name = file.filename or f"unnamed_{uuid.uuid4().hex}"
    output_prefix = uuid.uuid4().hex

    # 先上传原始文档到 MinIO，与后续结果在同一路径（异步，不阻塞事件循环）
    await build_async_minio_writer(output_prefix, MINIO_BUCKET_NAME).write(file_name, content)

    try:
        result = await parse_and_store(
            content=content,
            file_name=file_name,
            engine=engine,
            hybrid_opts=hybrid_opts,
            output_bucket=MINIO_BUCKET_NAME,
            output_prefix=output_prefix,
            f_dump_md=f_dump_md,
            f_dump_content_list=f_dump_content_list,
            f_dump_middle_json=f_dump_middle_json,
            f_dump_model_output=f_dump_model_output,
            f_dump_full_page_images=f_dump_full_page_images,
            f_dump_docx=f_dump_docx,
        )
        return JSONResponse(content=result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Parse failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/parse/minio",
    summary="从 MinIO 读取文档解析",
    description="""从 MinIO 指定路径读取文件并解析，结果写回同一 MinIO 路径。

**适用场景：** 文件已上传到 MinIO，只需传入 `doc_id`（路径前缀）和 `file_name` 即可。
其余参数与 `/parse` 一致。
""",
    response_description="同 /parse 接口",
)
async def parse_from_minio(
    doc_id: str = Form(..., description="MinIO 路径前缀（目录名 / UUID）"),
    file_name: str = Form(..., description="文件名，需与 doc_id 拼接后存在于 MinIO 中"),
    bucket_name: str = Form(..., description="MinIO Bucket 名称"),
    engine: EngineType = Form(EngineType.vlm, description="解析引擎：vlm（默认）/ hybrid / office"),
    hybrid_options: Optional[str] = Form(None, description="hybrid 引擎的 VLM 配置参数（JSON 字符串）"),
    f_dump_md: bool = Form(True, description="是否生成 Markdown"),
    f_dump_content_list: bool = Form(True, description="是否生成 content_list JSON"),
    f_dump_middle_json: bool = Form(True, description="是否写入 middle.json"),
    f_dump_model_output: bool = Form(True, description="是否写入 model.json"),
    f_dump_full_page_images: bool = Form(True, description="是否保存 PDF 每页全页图片"),
    f_dump_docx: bool = Form(False, description="[仅 PDF] 是否生成 Word 文档（.docx）"),
):
    hybrid_opts = parse_hybrid_options(hybrid_options)

    try:
        # 从 MinIO 读取原始文件内容（bucket_name/doc_id/file_name，异步）
        reader = build_async_minio_reader(doc_id, bucket_name)
        content = await reader.read(file_name)

        result = await parse_and_store(
            content=content,
            file_name=file_name,
            engine=engine,
            hybrid_opts=hybrid_opts,
            output_bucket=bucket_name,
            output_prefix=doc_id,
            f_dump_md=f_dump_md,
            f_dump_content_list=f_dump_content_list,
            f_dump_middle_json=f_dump_middle_json,
            f_dump_model_output=f_dump_model_output,
            f_dump_full_page_images=f_dump_full_page_images,
            f_dump_docx=f_dump_docx,
        )
        logger.info(f"MinIO parse complete: {doc_id}/{file_name}")
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"MinIO parse failed (doc_id={doc_id}): {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── 入口 ─────────────────────────────────────────────────
def main():
    import argparse, os, sys
    # 确保项目根目录在 sys.path 中，uv run 下也能正确导入 app 模块
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    parser = argparse.ArgumentParser(description="启动 OCR 解析服务")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址（默认 0.0.0.0）")
    parser.add_argument("--port", type=int, default=80, help="监听端口（默认 80）")
    parser.add_argument("--no-reload", action="store_true", help="关闭开发热重载（默认开启）")
    args = parser.parse_args()
    import uvicorn
    uvicorn.run("app.api.server:app", host=args.host, port=args.port, reload=not args.no_reload)


if __name__ == "__main__":
    main()
