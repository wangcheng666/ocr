# DOCX 编号处理指南

本指南面向 MinerU 开发者，系统说明 `DocxConverter` 中 DOCX 编号/列表的完整处理管线、输出数据结构、以及当前已知缺陷。所有结论均基于源码验证，文末附源码索引。

> 阅读前建议先了解 [middle_json 指南](./middle_json_guide.md) 和 [content_list_v2 指南](./content_list_v2_guide.md)，理解 list/title 块在下游的消费方式。

---

## 1. 概述

### 1.1 DOCX 编号机制

Word 的自动编号（如 "一、"、"1."、"a)"）**不是段落文本的一部分**，而是由 `word/numbering.xml` 中的编号定义驱动、由 Word 渲染引擎在显示时动态生成的。段落本身只存储一个编号引用（`numPr`），指向 numbering.xml 中的具体编号定义。

这意味着：解析 DOCX 时，段落的 `paragraph.text` 只包含用户实际输入的文字（如 "必要性分析"），不包含自动编号前缀（如 "一、"）。要还原完整的标题文本，必须读取 numbering.xml 并自行渲染编号。

### 1.2 核心 XML 结构

```
word/numbering.xml
├── <w:abstractNum w:abstractNumId="0">     ← 抽象编号定义（模板）
│   ├── <w:lvl w:ilvl="0">                  ← 层级 0 的定义
│   │   ├── <w:start w:val="1"/>            ← 起始值
│   │   ├── <w:numFmt w:val="chineseCounting"/>  ← 编号格式
│   │   ├── <w:lvlText w:val="%1、"/>       ← 编号文本模板
│   │   ├── <w:suff w:val="tab"/>           ← 编号与文本间的分隔符
│   │   └── <w:pStyle w:val="Heading1"/>    ← 关联的段落样式（可选）
│   ├── <w:lvl w:ilvl="1"> ... </w:lvl>    ← 层级 1
│   └── ...
├── <w:num w:numId="1">                     ← 编号实例（引用抽象定义）
│   ├── <w:abstractNumId w:val="0"/>        ← 指向 abstractNum
│   └── <w:lvlOverride w:ilvl="0">         ← 实例级覆盖（可选）
│       └── <w:startOverride w:val="3"/>    ← 覆盖起始值
└── ...

word/document.xml
└── <w:p>                                   ← 段落
    └── <w:pPr>
        └── <w:numPr>                       ← 编号引用
            ├── <w:ilvl w:val="0"/>         ← 缩进层级
            └── <w:numId w:val="1"/>        ← 编号实例 ID
```

### 1.3 DocxConverter 的处理目标

将 Word 的自动编号机制转换为 middle_json 的两种块结构：

- **list 块**：普通列表项（有序/无序），保留嵌套层级和起始编号
- **title 块**：被用作章节标题的列表项（如 "一、必要性分析"），转为带层级的标题

---

## 2. 核心概念

### 2.1 关键术语

| 术语 | 含义 | 示例 |
|------|------|------|
| `numId` | 编号实例 ID，段落通过它引用 numbering.xml 中的 `<w:num>` | `numId=1` |
| `ilvl` | 缩进层级（indent level），0 为最外层 | `ilvl=0` → 一级，`ilvl=1` → 二级 |
| `numFmt` | 编号格式，决定数字如何渲染 | `decimal` → 1,2,3；`chineseCounting` → 一,二,三 |
| `lvlText` | 编号文本模板，`%N` 为占位符（N = ilvl + 1） | `%1、` → "一、"；`%1.%2` → "1.1" |
| `suff` | 编号与段落文本间的分隔符 | `tab`（默认）/ `space` / `nothing` |
| `numPr` | 段落的编号属性，包含 `numId` 和 `ilvl` | 段落直接属性或样式继承 |
| `abstractNum` | 抽象编号定义（模板），被多个 `<w:num>` 实例共享 | `abstractNumId=0` |
| `lvlOverride` | 编号实例对抽象定义的覆盖 | 覆盖起始值 `startOverride` |

### 2.2 numPr 的来源

段落的 `numPr` 有两个来源，按优先级：

1. **段落直接属性**：`<w:p><w:pPr><w:numPr>` 中直接定义
2. **样式继承**：段落使用的样式（如 "List Paragraph"）的 `pPr` 中定义了 `numPr`

解析逻辑见 [`_get_effective_numPr`](file:///Users/wuyu/Documents/learning/czce-ai-ability/MinerU/mineru/model/docx/docx_converter.py#L2204-L2218)：先查段落直接属性，再沿样式继承链（`_iter_style_chain`）逐级查找。

### 2.3 numId=0 的特殊含义

`numId=0` 是 Word 中**显式取消编号**的信号。即使段落样式继承了 `numPr`，`numId=0` 也会覆盖它，表示该段落不参与编号。代码中在 [`_get_numId_and_ilvl`](file:///Users/wuyu/Documents/learning/czce-ai-ability/MinerU/mineru/model/docx/docx_converter.py#L2239-L2273) 返回后，将 `numid == 0` 设为 `None`（[L1435-L1436](file:///Users/wuyu/Documents/learning/czce-ai-ability/MinerU/mineru/model/docx/docx_converter.py#L1435-L1436)）。

### 2.4 abstractNum 与 num 的关系

```
abstractNum (模板)  ←──  num (实例1, numId=1)
                    ←──  num (实例2, numId=2, 带 lvlOverride)
```

- `abstractNum` 定义编号的格式模板（numFmt、lvlText、start 等）
- `num` 是具体实例，引用一个 `abstractNum`，并可通过 `lvlOverride` 覆盖部分属性
- 多个 `num` 可共享同一个 `abstractNum`，但各自有独立的起始值覆盖

---

## 3. 处理管线

### 3.1 初始化阶段

在 [`convert`](file:///Users/wuyu/Documents/learning/czce-ai-ability/MinerU/mineru/model/docx/docx_converter.py#L757) 入口处，所有列表相关状态被重置（[L764-L777](file:///Users/wuyu/Documents/learning/czce-ai-ability/MinerU/mineru/model/docx/docx_converter.py#L764-L777)）：

| 状态变量 | 初始值 | 用途 |
|----------|--------|------|
| `pre_num_id` | `-1` | 上一个处理元素的 numId |
| `pre_ilevel` | `-1` | 上一个处理元素的缩进等级 |
| `list_block_stack` | `[]` | 列表块堆栈（嵌套列表用） |
| `list_counters` | `{}` | 列表计数器 `(numId, ilvl) -> count` |
| `heading_list_numids` | `set()` | 用作章节标题的列表 numId 集合 |
| `_numbering_root` | `None` | numbering.xml 根元素缓存 |
| `_numbering_level_cache` | `{}` | `(numId, ilvl) -> lvl XML` 元素缓存 |
| `_numbering_start_cache` | `{}` | `(numId, ilvl) -> 起始值` 缓存 |

然后执行**预扫描**（[L787](file:///Users/wuyu/Documents/learning/czce-ai-ability/MinerU/mineru/model/docx/docx_converter.py#L787)）：

```python
self.heading_list_numids = self._detect_heading_list_numids()
```

### 3.2 段落处理阶段

每个段落的编号处理流程（[L1428-L1475](file:///Users/wuyu/Documents/learning/czce-ai-ability/MinerU/mineru/model/docx/docx_converter.py#L1428-L1475)）：

```
段落进入
  │
  ├─ _get_label_and_level() → (p_style_id, p_level)
  ├─ _get_numId_and_ilvl()  → (numid, ilevel)
  │
  ├─ numid == 0 ? → 设为 None（显式取消编号）
  │
  ├─ numid 和 ilevel 均非 None，且样式非 Title/Heading ?
  │   ├─ YES → 是列表段落
  │   │   ├─ numid ∈ heading_list_numids ?
  │   │   │   ├─ YES → 转为 TITLE 块（章节标题）
  │   │   │   └─ NO  → _add_list_item()（普通列表项）
  │   │   └─ return
  │   └─ NO → 继续
  │
  ├─ numid 为 None 且 pre_num_id != -1 ?
  │   └─ YES → _close_active_list()（列表结束）
  │
  └─ 按样式处理（Title / Heading / Normal / ...）
```

### 3.3 heading-style 列表检测算法

[`_detect_heading_list_numids`](file:///Users/wuyu/Documents/learning/czce-ai-ability/MinerU/mineru/model/docx/docx_converter.py#L2688-L2765) 在转换前预扫描整个文档，识别哪些 numId 的列表被用作章节标题。

**判断条件（需同时满足）**：

1. **正文穿插**：该 numId 的列表项之间穿插了非列表的正文内容（段落/表格）
2. **多级结构**：该 numId 的列表项出现在**多个不同的缩进层级**（`len(numid_ilvels) > 1`）

**算法流程**：

```
遍历文档 body 所有元素
  ├─ 段落（w:p）→ 提取 numid/ilevel/text
  │   ├─ 有 numid 且有文本 → items.append(("list", numid, ilevel))
  │   └─ 无 numid 且有文本 → items.append(("content",))
  └─ 表格（w:tbl）→ items.append(("content",))

对 items 序列做穿插检测：
  seen_numids[numid] = False  # 初始
  遇到 "list" 项：
    若 seen_numids[numid] == True → 满足条件1，加入 heading_numids
    重置 seen_numids[numid] = False
  遇到 "content" 项：
    所有 seen_numids[nid] = True

最终过滤：只保留 len(numid_ilvels[nid]) > 1 的 numId（条件2）
```

**设计意图**：避免将"多段内容条目之间穿插了小标签"的单级列表误判为标题列表。

### 3.4 普通列表项处理

[`_add_list_item`](file:///Users/wuyu/Documents/learning/czce-ai-ability/MinerU/mineru/model/docx/docx_converter.py#L2485) 根据 `pre_num_id` / `pre_ilevel` 与当前 `numid` / `ilevel` 的关系，分四种情况处理嵌套：

| 情况 | 条件 | 处理 | 行号 |
|------|------|------|------|
| 1. 新列表 | `pre_num_id == -1` 或 `pre_num_id != numid` | 关闭旧列表，创建新顶层 list block，入栈 | [L2540](file:///Users/wuyu/Documents/learning/czce-ai-ability/MinerU/mineru/model/docx/docx_converter.py#L2540) |
| 2. 增加缩进 | 同 numId 且 `pre_ilevel < ilevel` | 创建子 list block，附加到栈顶 content，入栈 | [L2566](file:///Users/wuyu/Documents/learning/czce-ai-ability/MinerU/mineru/model/docx/docx_converter.py#L2566) |
| 3. 减少缩进 | 同 numId 且 `ilevel < pre_ilevel` | 出栈直到找到匹配 ilevel 的块，附加列表项 | [L2616](file:///Users/wuyu/Documents/learning/czce-ai-ability/MinerU/mineru/model/docx/docx_converter.py#L2616) |
| 4. 同级 | 同 numId 且 `pre_ilevel == ilevel` | 直接附加到栈顶块的 content | [L2653](file:///Users/wuyu/Documents/learning/czce-ai-ability/MinerU/mineru/model/docx/docx_converter.py#L2653) |

### 3.5 列表关闭与计数器生命周期

[`_close_active_list`](file:///Users/wuyu/Documents/learning/czce-ai-ability/MinerU/mineru/model/docx/docx_converter.py#L792-L796) 重置列表状态，但**保留** `list_counters`：

```python
def _close_active_list(self) -> None:
    self.pre_num_id = -1
    self.pre_ilevel = -1
    self.list_block_stack = []
    # 注意：list_counters 不被清除
```

**设计意图**：Word 中同一 numId 的编号跨中断（表格、其他段落）时默认连续递增。保留计数器使编号在中断后继续（如 1,2,3 → 表格 → 4,5,6）。

**触发时机**：
- 遇到非列表段落且 `pre_num_id != -1`（[L1476-L1482](file:///Users/wuyu/Documents/learning/czce-ai-ability/MinerU/mineru/model/docx/docx_converter.py#L1476-L1482)）
- 遇到表格元素（[L895](file:///Users/wuyu/Documents/learning/czce-ai-ability/MinerU/mineru/model/docx/docx_converter.py#L895)）
- 遇到 TOC 段落（[L1420](file:///Users/wuyu/Documents/learning/czce-ai-ability/MinerU/mineru/model/docx/docx_converter.py#L1420)）
- 切换到不同 numId 的列表（情况1）

### 3.6 编号起始值解析

[`_get_numbering_level_start`](file:///Users/wuyu/Documents/learning/czce-ai-ability/MinerU/mineru/model/docx/docx_converter.py#L2388-L2421) 按以下优先级解析起始值：

1. `<w:num>` 下的 `<w:lvlOverride>` 中的 `<w:startOverride>`（实例级覆盖，最高优先）
2. `<w:abstractNum>` 下对应 `<w:lvl>` 中的 `<w:start>`（抽象定义级）
3. 默认值 `1`

[`_advance_list_counter`](file:///Users/wuyu/Documents/learning/czce-ai-ability/MinerU/mineru/model/docx/docx_converter.py#L2423-L2438) 推进计数器并返回当前序号：

- 首次出现 `(numId, ilvl)` → 使用 `_get_numbering_level_start()` 获取起始值
- 后续出现 → 当前值 + 1
- **子级重置**：父级 `(numId, ilvl)` 前进后，所有同 numId 下 `ilvl` 更大的计数器被删除

---

## 4. 输出数据结构

### 4.1 list 块

普通列表项生成的 list 块结构：

```json
{
    "type": "list",
    "attribute": "ordered",
    "ilevel": 0,
    "start": 1,
    "content": [
        {"type": "text", "content": "列表项文本"},
        {
            "type": "list",
            "attribute": "unordered",
            "ilevel": 1,
            "content": [
                {"type": "text", "content": "子列表项"}
            ]
        },
        {"type": "text", "content": "另一个列表项"}
    ]
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `attribute` | `"ordered"` / `"unordered"` | 由 `_is_numbered_list` 根据 numFmt 判断 |
| `ilevel` | `int` | Word 的缩进层级 |
| `start` | `int`（仅 ordered） | 起始编号，由 `_advance_list_counter` 返回 |
| `content` | `list` | 子块列表，可嵌套 list 块 |

### 4.2 title 块（heading-style 列表）

当 `numid ∈ heading_list_numids` 时，列表项转为 title 块（[L1447-L1464](file:///Users/wuyu/Documents/learning/czce-ai-ability/MinerU/mineru/model/docx/docx_converter.py#L1447-L1464)）：

```json
{
    "type": "title",
    "level": 1,
    "is_numbered_style": true,
    "content": "必要性分析"
}
```

| 字段 | 说明 |
|------|------|
| `level` | `ilevel + 1`（Word ilvl=0 → level=1 一级标题） |
| `is_numbered_style` | 由 `_is_numbered_list` 判断 |
| `content` | 段落文本（**不含自动编号前缀**，见缺陷 #1） |

### 4.3 下游渲染

[`_flatten_list_items`](file:///Users/wuyu/Documents/learning/czce-ai-ability/MinerU/mineru/backend/office/mkcontent/output_builders.py#L79-L101) 递归展平嵌套列表块，生成带前缀的文本行：

- 有序列表：`N. text`（N 从 `start` 开始递增）
- 无序列表：`- text`
- 缩进：`4空格 × relative_ilevel`

> **注意**：下游统一使用阿拉伯数字 `N.` 格式，不区分 numFmt。即使 Word 中是罗马数字或中文编号，输出也是 `1.` `2.` `3.`。

---

## 5. 编号格式支持（numFmt）

### 5.1 当前支持的格式

[`_is_numbered_list`](file:///Users/wuyu/Documents/learning/czce-ai-ability/MinerU/mineru/model/docx/docx_converter.py#L2440-L2483) 中 `numbered_formats` 集合（[L2470-L2477](file:///Users/wuyu/Documents/learning/czce-ai-ability/MinerU/mineru/model/docx/docx_converter.py#L2470-L2477)）：

| numFmt 值 | 渲染效果 | 示例 |
|-----------|----------|------|
| `decimal` | 阿拉伯数字 | 1, 2, 3 |
| `decimalZero` | 补零数字 | 01, 02, 03 |
| `lowerRoman` | 小写罗马数字 | i, ii, iii |
| `upperRoman` | 大写罗马数字 | I, II, III |
| `lowerLetter` | 小写字母 | a, b, c |
| `upperLetter` | 大写字母 | A, B, C |

不在此集合中的 numFmt（如 `bullet`）会被判定为**无序列表**。

### 5.2 当前不支持但常见的格式

以下 numFmt 值在 OOXML 规范中定义，但当前会被**错误地判定为无序列表**：

| numFmt 值 | 渲染效果 | 常见场景 |
|-----------|----------|----------|
| `chineseCounting` | 中文小写数字 | 一, 二, 三（中文文档章节标题） |
| `chineseCountingThousand` | 中文大写数字 | 壹, 贰, 叁（财务/法律文档） |
| `chineseLegal` | 中文法律数字 | 同 chineseCounting |
| `ideographTraditional` | 天干 | 甲, 乙, 丙 |
| `ideographDigital` | 中文数字（含〇） | 〇, 一, 二 |
| `japaneseCounting` | 日文数字 | 一, 二, 三 |
| `japaneseDigitalTenThousand` | 日文数字（含〇） | 〇, 一, 二 |
| `koreanCounting` | 韩文数字 | 일, 이, 삼 |
| `aiueo` / `iroha` | 日文假名 | あ, い, う |
| `lowerGreek` | 希腊字母 | α, β, γ |
| `ordinal` | 序数词 | 1st, 2nd, 3rd |
| `cardinalText` | 英文基数词 | one, two, three |
| `ordinalText` | 英文序数词 | first, second, third |
| `decimalEnclosedCircle` | 带圈数字 | ①, ②, ③ |
| `hex` | 十六进制 | 1, 2, …, A, B |
| `chicago` | 芝加哥手册格式 | *, †, ‡ |

---

## 6. 已知缺陷与边界情况

### 缺陷 #1：heading-style 列表转 title 时丢失自动编号前缀（严重）

**现象**：段落 "一、必要性分析" 被转为 title 块后，content 只有 "必要性分析"，"一、" 丢失。

**原因**：[L1452-L1453](file:///Users/wuyu/Documents/learning/czce-ai-ability/MinerU/mineru/model/docx/docx_converter.py#L1452-L1453) 中 `content_text` 只从段落的文本 run 中提取，而 "一、" 是 Word numbering.xml 定义的自动编号，不在段落文本中。代码没有读取 numbering 定义来还原编号前缀。

**影响**：所有使用 Word 自动编号的章节标题（如 "一、"、"（一）"、"1."）在转为 title 块后丢失编号。

**修复方向**：在创建 title 块时，读取 `lvlText` 模板和 `numFmt`，调用 `_advance_list_counter` 获取当前序号，格式化后拼接到 content 前面。

### 缺陷 #2：`_is_numbered_list` 不识别中文/日文等编号格式（严重）

**现象**：使用 `chineseCounting`（一、二、三）等中文编号格式的列表被判定为无序列表，`is_numbered_style` 为 `false`。

**原因**：[L2470-L2477](file:///Users/wuyu/Documents/learning/czce-ai-ability/MinerU/mineru/model/docx/docx_converter.py#L2470-L2477) 的 `numbered_formats` 集合只包含 6 种西文格式。

**影响**：中文文档中最常见的 "一、二、三" 和 "（一）（二）（三）" 编号格式全部被误判为无序列表。

**修复方向**：将 `chineseCounting`、`chineseCountingThousand`、`chineseLegal`、`ideographTraditional`、`ideographDigital`、`japaneseCounting`、`japaneseDigitalTenThousand` 等加入 `numbered_formats`。

### 缺陷 #3：下游渲染统一用阿拉伯数字（中等）

**现象**：即使 `_is_numbered_list` 正确识别了 `lowerRoman` 格式，最终输出也是 `1.` `2.` 而非 `i.` `ii.`。

**原因**：[`_flatten_list_items`](file:///Users/wuyu/Documents/learning/czce-ai-ability/MinerU/mineru/backend/office/mkcontent/output_builders.py#L79-L101) 只使用 `start` 整数值生成 `N.` 前缀，不感知 numFmt。list 块的数据结构中也没有存储 numFmt 信息。

**影响**：罗马数字、字母、中文编号在最终输出中全部变成阿拉伯数字。

**修复方向**：在 list 块中增加 `numFmt` 字段，下游根据 numFmt 格式化编号。

### 缺陷 #4：`_detect_heading_list_numids` 条件2过严（中等）

**现象**：若文档中所有章节标题恰好都在同一缩进层级（如全部 `ilvl=0`），即使有正文穿插也不会被识别为标题列表。

**原因**：[L2753-L2758](file:///Users/wuyu/Documents/learning/czce-ai-ability/MinerU/mineru/model/docx/docx_converter.py#L2753-L2758) 要求 `len(numid_ilvels[nid]) > 1`，即必须出现多种缩进层级。

**影响**：只有一级标题（无二级、三级子标题）的文档中，标题列表不会被识别，列表项被当作普通列表处理而非 title 块。

**设计权衡**：条件2 是为了避免将单级内容条目列表误判为标题。放宽条件可能导致误判。

### 缺陷 #5：`_get_numbering_level_definition` 不处理 lvlOverride 完整覆盖（低）

**现象**：OOXML 规范允许 `<w:lvlOverride>` 包含完整的 `<w:lvl>` 子元素来覆盖 abstractNum 的定义（不仅是 `startOverride`），但当前代码只处理了 `startOverride`。

**原因**：[`_get_numbering_level_definition`](file:///Users/wuyu/Documents/learning/czce-ai-ability/MinerU/mineru/model/docx/docx_converter.py#L2364-L2386) 只从 `abstractNum` 中查找 `<w:lvl>`，不检查 `<w:num>` 中 `lvlOverride` 的完整覆盖。

**影响**：若 Word 文档通过 lvlOverride 覆盖了 numFmt 或 lvlText，解析结果会使用 abstractNum 的原始定义而非覆盖值。实际文档中这种情况较少见。

### 缺陷 #6：`_add_list_item` 减少缩进时栈为空导致列表拆分（低）

**现象**：减少缩进时（情况3），若出栈后找不到匹配 ilevel 的块，会创建新的顶层列表块，导致同一个 Word 列表被拆分成多个独立的 list block。

**原因**：[L2628-L2642](file:///Users/wuyu/Documents/learning/czce-ai-ability/MinerU/mineru/model/docx/docx_converter.py#L2628-L2642) 中栈为空时的回退处理。

**影响**：编号可能不连续（两个 list block 各自从 start 开始计数）。

### 缺陷 #7：`_close_active_list` 保留计数器的设计影响（低）

**现象**：同一 numId 的列表被表格或其他段落中断后，编号继续递增（如 1,2,3 → 表格 → 4,5,6），即使 Word 文档中实际是重新编号的。

**原因**：[`_close_active_list`](file:///Users/wuyu/Documents/learning/czce-ai-ability/MinerU/mineru/model/docx/docx_converter.py#L792-L796) 不清除 `list_counters`。

**设计权衡**：保留计数器符合 Word 的默认行为（同 numId 跨中断连续编号）。若 Word 文档通过 `startOverride` 指定了重新编号，`_get_numbering_level_start` 的缓存机制可能导致问题——缓存只在首次查询时填充，之后不会更新。

### 缺陷 #8：无单元测试覆盖（中等）

**现象**：项目中没有针对编号逻辑的单元测试。`MinerU/tests/` 下只有 `test_e2e.py`（PDF 端到端测试），不涉及 DOCX numbering。

**影响**：编号逻辑的修改无回归保障，容易引入隐蔽 bug。

**建议**：为以下方法添加单元测试：
- `_is_numbered_list`：各种 numFmt 的判断
- `_advance_list_counter`：计数器递增、子级重置
- `_detect_heading_list_numids`：穿插检测、多级过滤
- `_add_list_item`：四种嵌套情况
- `_get_numbering_level_start`：优先级解析

---

## 7. 源码索引

### docx_converter.py

文件路径：`MinerU/mineru/model/docx/docx_converter.py`

| 方法 | 行号 | 说明 |
|------|------|------|
| [`convert`](file:///Users/wuyu/Documents/learning/czce-ai-ability/MinerU/mineru/model/docx/docx_converter.py#L757) | L757 | 转换入口，重置状态 + 预扫描 |
| [`_close_active_list`](file:///Users/wuyu/Documents/learning/czce-ai-ability/MinerU/mineru/model/docx/docx_converter.py#L792) | L792 | 关闭活跃列表，保留计数器 |
| [`_get_label_and_level`](file:///Users/wuyu/Documents/learning/czce-ai-ability/MinerU/mineru/model/docx/docx_converter.py#L2140) | L2140 | 获取段落样式 ID 和层级 |
| [`_get_effective_numPr`](file:///Users/wuyu/Documents/learning/czce-ai-ability/MinerU/mineru/model/docx/docx_converter.py#L2204) | L2204 | 解析有效 numPr（直接属性 + 样式继承） |
| [`_get_numId_and_ilvl`](file:///Users/wuyu/Documents/learning/czce-ai-ability/MinerU/mineru/model/docx/docx_converter.py#L2239) | L2239 | 提取 numId 和 ilvl 整数值 |
| [`_get_numbering_num_element`](file:///Users/wuyu/Documents/learning/czce-ai-ability/MinerU/mineru/model/docx/docx_converter.py#L2275) | L2275 | 按 numId 查找 `<w:num>` 元素 |
| [`_get_abstract_numbering_element`](file:///Users/wuyu/Documents/learning/czce-ai-ability/MinerU/mineru/model/docx/docx_converter.py#L2289) | L2289 | 从 numId 追溯到 `<w:abstractNum>` |
| [`_infer_numbering_ilvl_from_style`](file:///Users/wuyu/Documents/learning/czce-ai-ability/MinerU/mineru/model/docx/docx_converter.py#L2317) | L2317 | 通过 pStyle 映射反查编号层级 |
| [`_get_numbering_root`](file:///Users/wuyu/Documents/learning/czce-ai-ability/MinerU/mineru/model/docx/docx_converter.py#L2347) | L2347 | 加载并缓存 numbering.xml |
| [`_get_numbering_level_definition`](file:///Users/wuyu/Documents/learning/czce-ai-ability/MinerU/mineru/model/docx/docx_converter.py#L2364) | L2364 | 获取 (numId, ilvl) 的 lvl 定义 |
| [`_get_numbering_level_start`](file:///Users/wuyu/Documents/learning/czce-ai-ability/MinerU/mineru/model/docx/docx_converter.py#L2388) | L2388 | 解析编号起始值（带优先级） |
| [`_advance_list_counter`](file:///Users/wuyu/Documents/learning/czce-ai-ability/MinerU/mineru/model/docx/docx_converter.py#L2423) | L2423 | 推进计数器，返回当前序号 |
| [`_is_numbered_list`](file:///Users/wuyu/Documents/learning/czce-ai-ability/MinerU/mineru/model/docx/docx_converter.py#L2440) | L2440 | 判断有序/无序（基于 numFmt） |
| [`_add_list_item`](file:///Users/wuyu/Documents/learning/czce-ai-ability/MinerU/mineru/model/docx/docx_converter.py#L2485) | L2485 | 核心：添加列表项（四种嵌套情况） |
| [`_detect_heading_list_numids`](file:///Users/wuyu/Documents/learning/czce-ai-ability/MinerU/mineru/model/docx/docx_converter.py#L2688) | L2688 | 预扫描：检测 heading-style 列表 |

### output_builders.py

文件路径：`MinerU/mineru/backend/office/mkcontent/output_builders.py`

| 方法 | 行号 | 说明 |
|------|------|------|
| [`_get_ordered_list_start`](file:///Users/wuyu/Documents/learning/czce-ai-ability/MinerU/mineru/backend/office/mkcontent/output_builders.py#L58) | L58 | 获取有序列表起始值 |
| [`_get_list_ilevel`](file:///Users/wuyu/Documents/learning/czce-ai-ability/MinerU/mineru/backend/office/mkcontent/output_builders.py#L66) | L66 | 获取列表缩进层级 |
| [`_flatten_list_items`](file:///Users/wuyu/Documents/learning/czce-ai-ability/MinerU/mineru/backend/office/mkcontent/output_builders.py#L79) | L79 | v1：递归展平列表为前缀文本行 |
| [`_flatten_list_items_v2`](file:///Users/wuyu/Documents/learning/czce-ai-ability/MinerU/mineru/backend/office/mkcontent/output_builders.py#L104) | L104 | v2：递归展平列表为结构化 dict |
| [`merge_list_to_markdown`](file:///Users/wuyu/Documents/learning/czce-ai-ability/MinerU/mineru/backend/office/mkcontent/output_builders.py#L138) | L138 | 列表块转 Markdown 文本 |
