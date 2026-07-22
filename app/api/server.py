"""MinerU Custom API Server"""

from pathlib import Path

from dotenv import load_dotenv

# 加载 workspace 根目录的 .env 文件
load_dotenv(Path(__file__).parents[2] / ".env")

from fastapi import FastAPI

app = FastAPI(title="MinerU Custom Server")


@app.get("/health")
async def health():
    return {"status": "ok"}


def main():
    import uvicorn
    uvicorn.run("api.server:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
