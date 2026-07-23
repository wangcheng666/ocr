"""MinerU Custom API Server — Controller"""

import os
import tempfile
import uuid
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv(Path(__file__).parents[2] / ".env")

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from loguru import logger

from mineru.data.data_reader_writer import FileBasedDataWriter

from ..config.settings import (
    VLM_BACKEND,
    VLM_SERVER_URL,
    MINERU_CUT_IMAGES_DIR,
    MINIO_ENDPOINT,
    MINIO_ACCESS_KEY,
    MINIO_SECRET_KEY,
    MINIO_BUCKET_NAME,
)
from ..service.engine import (
    EngineType,
    core_parse,
    parse_hybrid_options,
)
from ..service.output import write_outputs_to_minio, pack_and_upload_zip, make_md, build_output_file_list
from mineru.utils.enum_class import MakeMode

from ..service.storage import (
    build_minio_writer,
    build_minio_reader,
    check_minio_configured,
)

from .ocr_router import router as ocr_router


# ── FastAPI 应用 ─────────────────────────────────────────
app = FastAPI(title="MinerU Custom Server")
app.include_router(ocr_router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/parse")
async def parse_document(
    file: UploadFile = File(...),
    engine: EngineType = EngineType.hybrid,
    hybrid_options: Optional[str] = Form(None),
    f_dump_md: bool = Form(True),
    f_dump_content_list: bool = Form(True),
    f_dump_middle_json: bool = Form(True),
    f_dump_model_output: bool = Form(True),
    f_dump_full_page_images: bool = Form(True),
):
    """
    上传文档解析，返回结果

    结果写入 MinIO 临时路径 `tmp/{uuid}/`，打包为 ZIP，仅返回下载链接。
    若 MinIO 未配置则仅返回 JSON 内容。
    """
    hybrid_opts = parse_hybrid_options(hybrid_options)
    content = await file.read()
    file_name = file.filename or f"unnamed_{uuid.uuid4().hex}"
    stem = ".".join(file_name.split(".")[:-1]) or file_name

    minio_ready = all([MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY, MINIO_BUCKET_NAME])

    if minio_ready:
        temp_prefix = f"tmp/{uuid.uuid4().hex}"
        image_writer = build_minio_writer(os.path.join(temp_prefix, MINERU_CUT_IMAGES_DIR), MINIO_BUCKET_NAME)
    else:
        tmp_dir_obj = tempfile.TemporaryDirectory()
        image_writer = FileBasedDataWriter(os.path.join(tmp_dir_obj.name, "images"))

    try:
        middle_json, model_output, file_type = core_parse(
            content, file_name, engine, hybrid_opts, image_writer,
        )

        result = {
            "status": "success",
            "file_name": file_name,
            "file_type": file_type,
            "engine": engine.value,
            "vlm_backend": VLM_BACKEND,
            "server_url": VLM_SERVER_URL or None,
            "page_count": len(middle_json.get("pdf_info", [])),
            "pdf_info": middle_json.get("pdf_info", []),
            "content": make_md(middle_json.get("pdf_info", []), MakeMode.MM_MD),
        }

        if minio_ready:
            # ── 写入输出文件到 MinIO ─────────────────────
            file_writer = build_minio_writer(temp_prefix, MINIO_BUCKET_NAME)
            write_outputs_to_minio(
                writer=file_writer,
                stem=stem,
                middle_json=middle_json,
                model_output=model_output,
                file_info=middle_json.get("pdf_info"),
                cut_images_dir=MINERU_CUT_IMAGES_DIR,
                pdf_bytes=content if file_type == "pdf" else None,
                f_dump_md=f_dump_md,
                f_dump_content_list=f_dump_content_list,
                f_dump_middle_json=f_dump_middle_json,
                f_dump_model_output=f_dump_model_output,
                f_dump_full_page_images=f_dump_full_page_images,
            )

            # ── 打包 ZIP ─────────────────────────────────
            reader = build_minio_reader(temp_prefix, MINIO_BUCKET_NAME)
            page_count = len(middle_json.get("pdf_info", []))
            files = build_output_file_list(
                stem=stem,
                f_dump_md=f_dump_md,
                f_dump_content_list=f_dump_content_list,
                f_dump_middle_json=f_dump_middle_json,
                f_dump_model_output=f_dump_model_output,
                f_dump_full_page_images=f_dump_full_page_images,
                page_count=page_count,
            )
            zip_name = pack_and_upload_zip(
                reader=reader,
                writer=file_writer,
                prefix=temp_prefix,
                stem=stem,
                files=files,
            )

            download_url = f"http://{MINIO_ENDPOINT}/{MINIO_BUCKET_NAME}/{temp_prefix}/{zip_name}"
            result["download_url"] = download_url

        return JSONResponse(content=result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Parse failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if not minio_ready:
            tmp_dir_obj.cleanup()


@app.post("/parse/minio")
async def parse_from_minio(
    doc_id: str = Form(...),
    file_name: str = Form(...),
    bucket_name: str = Form(...),
    engine: EngineType = EngineType.hybrid,
    hybrid_options: Optional[str] = Form(None),
    f_dump_md: bool = Form(True),
    f_dump_content_list: bool = Form(True),
    f_dump_middle_json: bool = Form(True),
    f_dump_model_output: bool = Form(True),
    f_dump_full_page_images: bool = Form(True),
):
    """从 MinIO 读取文档并解析，结果写回 MinIO"""
    check_minio_configured()

    hybrid_opts = parse_hybrid_options(hybrid_options)

    content = build_minio_reader(doc_id, bucket_name).read(file_name)
    if not content:
        raise HTTPException(status_code=404, detail=f"File '{file_name}' not found in MinIO")

    file_writer = build_minio_writer(doc_id, bucket_name)
    image_writer = build_minio_writer(os.path.join(doc_id, MINERU_CUT_IMAGES_DIR), bucket_name)

    try:
        middle_json, model_output, file_type = core_parse(
            content, file_name, engine, hybrid_opts, image_writer,
        )

        stem = ".".join(file_name.split(".")[:-1]) or file_name
        write_outputs_to_minio(
            writer=file_writer,
            stem=stem,
            middle_json=middle_json,
            model_output=model_output,
            file_info=middle_json.get("pdf_info"),
            cut_images_dir=MINERU_CUT_IMAGES_DIR,
            pdf_bytes=content if file_type == "pdf" else None,
            f_dump_md=f_dump_md,
            f_dump_content_list=f_dump_content_list,
            f_dump_middle_json=f_dump_middle_json,
            f_dump_model_output=f_dump_model_output,
            f_dump_full_page_images=f_dump_full_page_images,
        )
        logger.info(f"MinIO parse complete: {doc_id}/{stem}")

        return JSONResponse(content={
            "status": "success",
            "doc_id": doc_id,
            "file_name": file_name,
            "file_type": file_type,
            "engine": engine.value,
            "vlm_backend": VLM_BACKEND,
            "server_url": VLM_SERVER_URL or None,
            "page_count": len(middle_json.get("pdf_info", [])),
            "output_path": f"{bucket_name}/{doc_id}/{stem}_middle.json",
        })
    except Exception as e:
        logger.error(f"MinIO parse failed (doc_id={doc_id}): {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── 入口 ─────────────────────────────────────────────────
def main():
    import uvicorn
    uvicorn.run("api.server:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
