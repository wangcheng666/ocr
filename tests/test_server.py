"""Server 启动与健康检查测试"""

import os
import sys
from pathlib import Path

# 将项目根目录加入 sys.path
PROJECT_ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

# 确保 app 作为包可导入
_PKG = Path(__file__).parents[1]
if str(_PKG) not in sys.path:
    sys.path.insert(0, str(_PKG))

TEST_DATA_DIR = Path(__file__).parent / "data"
DEMO_PDF = TEST_DATA_DIR / "pdf" / "test_demo.pdf"


def test_health():
    """验证 FastAPI 应用可正常导入，/health 路由存在"""
    from app.api.server import app

    routes = {r.path for r in app.routes if hasattr(r, "path")}
    assert "/health" in routes, "/health route not found"


def test_all_routes():
    """验证所有预期路由已注册"""
    from app.api.server import app

    # 通过 OpenAPI schema 获取所有路由（包含 IncludedRouter 的子路由）
    spec = app.openapi()
    routes = set(spec.get("paths", {}).keys())

    expected = {"/health", "/parse", "/parse/minio"}
    for route in expected:
        assert route in routes, f"Route {route} not found (got {sorted(routes)})"
    print(f"All {len(expected)} routes registered: {sorted(expected)}")


def test_demo_pdf_exists():
    """验证测试 PDF 存在"""
    assert DEMO_PDF.exists(), f"Test PDF not found: {DEMO_PDF}"
    assert DEMO_PDF.stat().st_size > 0, f"Test PDF is empty: {DEMO_PDF}"
    print(f"Test PDF ready: {DEMO_PDF} ({DEMO_PDF.stat().st_size} bytes)")


if __name__ == "__main__":
    test_health()
    test_all_routes()
    test_demo_pdf_exists()
    print("\nAll basic tests passed!")
