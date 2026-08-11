# VLM 模型输出 block 类型

> 适用引擎：`vlm`（同 `hybrid`）。三层结构：**模型原始输出（model.json）→ 后处理 → middle.json**。

## 1. 模型原始输出（`{stem}_model.json`）— 27 种类型

来源：`mineru_vl_utils/structs.py` 的 `BLOCK_TYPES`（`ContentBlock` 构造时校验）。

| 分类 | type |
|---|---|
| 正文 | `text` `title` `table` `equation` `formula_number` `code` `algorithm` `ref_text` `index` `phonetic` `list_item` `aside_text` |
| 标题 | `table_caption` `image_caption` `code_caption` |
| 脚注 | `table_footnote` `image_footnote` |
| 页眉页脚 | `header` `footer` `page_number` `page_footnote` |
| 图片类 | `image` `chart` |
| 容器类 | `list` `image_block` `equation_block` |
| 其他 | `unknown` |

## 2. 模型后处理（`post_process`）的转换

- **image/chart 图像分析**：`pure_table`→`table`、`pure_formula`→`equation`、`chart`→`chart`(带 `sub_type`)、其余→`image`(带 `sub_type`)
- `list_item` → `text`
- `equation_block` → 拆成独立 `equation` 后丢弃
- `unknown` 归入 `PARATEXT_TYPES`（与 header/footer 等同组）
- table 内容 OTSL → HTML

## 3. 最终 middle.json — 一棵完整的树

由 `MinerU/mineru/backend/vlm/vlm_magic_model.py` 的 `MagicModel` 映射。整体就是**一棵树**：`middle.json → 页面 → 主块 → 子块 → 行 → 字块(span)`。

```
middle.json
├─ _backend / _version_name
└─ pdf_info[]  ······························· 每页一棵子树
    └─ 页面
        ├─ page_idx / page_size
        │
        ├─ para_blocks[]  ···················· 参与渲染的主块
        │   ├─ image  ← 模型 image / image_block ── 图片
        │   │   ├─ image_body      → span{image_path}   本体
        │   │   ├─ image_caption   → span{text}         标题
        │   │   └─ image_footnote  → span{text}         脚注
        │   ├─ table  ← 模型 table ── 表格
        │   │   ├─ table_body      → span{html}
        │   │   ├─ table_caption   → span{text}
        │   │   └─ table_footnote  → span{text}
        │   ├─ chart  ← 模型 chart ── 图表
        │   │   ├─ chart_body      → span{image_path}
        │   │   ├─ chart_caption   → span{text}
        │   │   └─ chart_footnote  → span{text}
        │   ├─ code  ← 模型 code / algorithm ── 代码/算法
        │   │   ├─ code_body       → span{text}（sub_type=code/algorithm，code 带 guess_lang）
        │   │   ├─ code_caption    → span{text}
        │   │   └─ code_footnote   → span{text}
        │   ├─ title              ← title       ── 标题（带 section_number）
        │   ├─ text               ← text        ── 正文
        │   ├─ ref_text           ← ref_text    ── 参考文献
        │   ├─ phonetic           ← phonetic    ── 注音
        │   ├─ list               ← list        ── 列表（子块为 text）
        │   └─ interline_equation ← equation    ── 行间公式
        │
        └─ discarded_blocks[]  ················ 不参与渲染
            ├─ header / footer / page_number   ← 页眉 / 页脚 / 页码
            └─ aside_text / page_footnote      ← 侧栏 / 脚注

每个块都挂 lines[] → spans[]，span 是树的叶子（携带内容）：
span
├─ text               纯文本      （content）
├─ inline_equation    行内公式    （content）
├─ interline_equation 行间公式    （content）
├─ image              图片        （image_path）
└─ table              表格        （html）
```

> 记忆法：**块**决定是什么，**子块**决定是本体/标题/脚注，**字块(span)** 决定内容形态。
> 子块不一定全出现：常只有 `*_body`，识别到标题/脚注时才有 caption/footnote。

## 核心结论

- **model.json**：模型识别的 27 种原始类型（`f_dump_model_output=true` 时写入）。
- **middle.json**：归一化后的 10 类块 + `discarded`。
- `formula_number` / `index` / `unknown` 无显式映射，经后处理转换或被丢弃，**最终 middle.json 基本不出现**。
