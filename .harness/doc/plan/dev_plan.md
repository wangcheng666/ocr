# ocr 项目 — 开发计划

## 目标
使用 uv workspace 将项目组织为统一 `ocr` 父目录下的多模块结构。

## 目录结构

```
/home/czce/Documents/code/python/
└── ocr/                          ← workspace 根（仅编排，不是包）
    ├── pyproject.toml            ← workspace 声明
    ├── uv.lock                   ← 全局统一 lock
    │
    ├── MinerU/                   ← 引擎库（官方原样，不动）
    │   ├── mineru/
    │   └── pyproject.toml
    │
    └── app/                      ← 自定义 FastAPI 应用
        ├── pyproject.toml        ← name = "mineru-server"
        │                           deps = [ mineru, fastapi, uvicorn, ... ]
        └── api/
            ├── __init__.py
            └── server.py         ← FastAPI 入口
```

## 依赖关系

```
app
 ├── mineru         ← workspace 路径引用 → ../MinerU/
 ├── fastapi
 ├── uvicorn
 └── python-multipart
```

MinerU 保持官方原样，fastapi/uvicorn 为其自带的 `mineru-api` / `mineru-router` 命令服务。

## 计划步骤

### Phase 1: workspace 初始化  ✅
- [x] 创建 `ocr/pyproject.toml` workspace 根
- [x] 创建 `app/pyproject.toml` 项目配置
- [x] 搭建 `app/api/server.py` FastAPI 骨架（含 `/health`）
- [x] 运行 `uv sync` 初始化统一环境

### Phase 2: Server 基础框架
- [ ] ...

---

> 按需逐步补充。
