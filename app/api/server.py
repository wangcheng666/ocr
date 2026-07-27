"""MinerU Custom API Server — Controller"""

import uuid
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv(Path(__file__).parents[2] / ".env")

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from loguru import logger

from ..config.settings import MINIO_BUCKET_NAME
from ..service.engine import EngineType, parse_hybrid_options
from ..service.orchestrator import parse_and_store
from ..service.storage import build_minio_reader, build_minio_writer


# ── FastAPI 应用 ─────────────────────────────────────────
app = FastAPI(title="MinerU Custom Server")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/parse")
async def parse_document(
    file: UploadFile = File(...),
    engine: EngineType = Form(EngineType.hybrid),
    hybrid_options: Optional[str] = Form(None),
    f_dump_md: bool = Form(True),
    f_dump_content_list: bool = Form(True),
    f_dump_middle_json: bool = Form(True),
    f_dump_model_output: bool = Form(True),
    f_dump_full_page_images: bool = Form(True),
):
    """上传文档解析，结果写入 MinIO（原始文档一并保存）"""
    hybrid_opts = parse_hybrid_options(hybrid_options)
    content = await file.read()
    file_name = file.filename or f"unnamed_{uuid.uuid4().hex}"
    output_prefix = uuid.uuid4().hex

    # 先上传原始文档到 MinIO，与后续结果在同一路径
    build_minio_writer(output_prefix, MINIO_BUCKET_NAME).write(file_name, content)

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
        )
        return JSONResponse(content=result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Parse failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/parse/minio")
async def parse_from_minio(
    doc_id: str = Form(...),
    file_name: str = Form(...),
    bucket_name: str = Form(...),
    engine: EngineType = Form(EngineType.hybrid),
    hybrid_options: Optional[str] = Form(None),
    f_dump_md: bool = Form(True),
    f_dump_content_list: bool = Form(True),
    f_dump_middle_json: bool = Form(True),
    f_dump_model_output: bool = Form(True),
    f_dump_full_page_images: bool = Form(True),
):
    """从 MinIO 读取文档并解析，结果写回同一路径"""
    hybrid_opts = parse_hybrid_options(hybrid_options)

    content = build_minio_reader(doc_id, bucket_name).read(file_name)
    if not content:
        raise HTTPException(status_code=404, detail=f"File '{file_name}' not found in MinIO")

    try:
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
        )
        logger.info(f"MinIO parse complete: {doc_id}/{file_name}")
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"MinIO parse failed (doc_id={doc_id}): {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── 入口 ─────────────────────────────────────────────────
def main():
    import uvicorn
    uvicorn.run("api.server:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
