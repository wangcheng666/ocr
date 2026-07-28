# DOCX 编号处理缺陷修改计划

## 验证结论

已逐一比对问题描述文档与 `MinerU/mineru/model/docx/docx_converter.py` 和 `MinerU/mineru/backend/office/mkcontent/output_builders.py` 的实际源码，**8 项缺陷全部属实**。以下按优先级排序制定修改计划。

---

## 修改优先级

| 优先级 | 缺陷 | 影响面 | 工作量估计 |
|--------|------|--------|-----------|
| **P0** | #2 `_is_numbered_list` 不识别中文/日文等编号格式 | 中文文档中"一、二、三"误判为无序列表 | 小（1 行集合扩增） |
| **P0** | #1 heading-style 列表转 title 时丢失自动编号前缀 | 章节标题丢失编号，语义不完整 | 中（需拼接编号前缀） |
| **P1** | #3 下游渲染统一用阿拉伯数字 | 罗马/字母/中文编号最终全部变数字 | 中（增加 numFmt 传递+格式化） |
| **P1** | #8 无单元测试覆盖 | 修改无回归保障 | 大（需搭建测试框架） |
| **P2** | #4 `_detect_heading_list_numids` 条件2过严 | 单级标题列表不被识别 | 小（放宽过滤条件） |
| **P3** | #5 `_get_numbering_level_definition` 不处理 lvlOverride 完整覆盖 | 罕见场景，实例级格式覆盖无效 | 中（需改造查找逻辑） |
| **P3** | #6 `_add_list_item` 减少缩进时栈为空导致列表拆分 | 畸形嵌套文档中列表分裂 | 小（改进回退策略） |
| **P3** | #7 `_close_active_list` 保留计数器的设计影响 | 跨中断重新编号场景 | 小（增加可选重置） |

---

## 详细修改方案

### P0-1: `_is_numbered_list` 扩充 `numbered_formats`（缺陷 #2）

**目标文件**: `MinerU/mineru/model/docx/docx_converter.py`

**修改位置**: `_is_numbered_list` 方法中 `numbered_formats` 集合（当前 L2470-L2477）

**变更内容**:
```python
numbered_formats = {
    "decimal",
    "decimalZero",
    "lowerRoman",
    "upperRoman",
    "lowerLetter",
    "upperLetter",
    # 中文编号格式
    "chineseCounting",          # 一, 二, 三
    "chineseCountingThousand",  # 壹, 贰, 叁
    "chineseLegal",             # 中文法律数字（同 chineseCounting）
    "ideographTraditional",     # 甲, 乙, 丙
    "ideographDigital",         # 〇, 一, 二
    # 日文编号格式
    "japaneseCounting",         # 一, 二, 三
    "japaneseDigitalTenThousand",  # 〇, 一, 二
    "aiueo",                    # あ, い, う
    "iroha",                    # い, ろ, は
    # 韩文编号格式
    "koreanCounting",           # 일, 이, 삼
    "koreanDigital",            # 〇, 一, 二
    # 其他常见格式
    "ordinal",                  # 1st, 2nd, 3rd
    "cardinalText",             # one, two, three
    "ordinalText",              # first, second, third
    "decimalEnclosedCircle",    # ①, ②, ③
    "decimalEnclosedFullstop",  # 1., 2., 3.
    "decimalEnclosedParen",     # (1), (2), (3)
    "lowerGreek",               # α, β, γ
    "hex",                      # 十六进制
    "chicago",                  # *, †, ‡
}
```

**影响范围**: 仅修改有序/无序判断逻辑，不涉及数据结构变更。修改后 `is_numbered_style` 和列表 `attribute` 字段会正确标记为 `"ordered"`。

---

### P0-2: heading-style 列表转 title 时还原自动编号前缀（缺陷 #1）

**目标文件**: `MinerU/mineru/model/docx/docx_converter.py`

**修改位置**: `convert` 方法中 heading-style 列表处理分支（当前 L1447-L1464）

**变更内容**:

在创建 `title_block` 之前，新增编号前缀生成逻辑：

```python
# 读取 lvlText 模板和 numFmt，生成编号前缀
numbering_prefix = self._render_numbering_prefix(numid, ilevel)
if numbering_prefix:
    content_text = numbering_prefix + content_text
```

**新增辅助方法 `_render_numbering_prefix`**:

```python
def _render_numbering_prefix(self, numId: int, ilvl: int) -> str:
    """根据 numId/ilvl 渲染自动编号前缀（如一、 (1) a) 等）。
    
    从 numbering.xml 中读取 lvlText 模板和 numFmt，
    调用 _advance_list_counter 获取当前序号值，
    将序号值填入 lvlText 模板中的 %N 占位符，生成完整前缀。
    """
```

**实现要点**:
1. 调用 `_get_numbering_level_definition(numId, ilvl)` 获取 `<w:lvl>` 元素
2. 读取 `<w:lvlText>` 的 `val` 属性（如 `"%1、"`、`"(%1)"`、`"%1.%2"`）
3. 读取 `<w:numFmt>` 的 `val` 属性确定格式化方式
4. 调用 `_advance_list_counter(numId, ilvl)` 获取当前序号整数值
5. 根据 numFmt 将序号值格式化为对应格式（如 `1→"一"`, `1→"①"`）
6. 替换 lvlText 中的 `%N` 占位符（N = ilvl+1, ilvl+2, ...）
7. 返回生成的前缀字符串（如 `"一、"`、`"(1)"`、`"1.1"`）

**新增辅助方法 `_format_number_by_numfmt`**:

```python
def _format_number_by_numfmt(self, number: int, numFmt: str) -> str:
    """将整数序号按 numFmt 格式化为对应的编号字符串。
    
    例如：
    - decimal: 1, 2, 3
    - chineseCounting: 一, 二, 三
    - lowerRoman: i, ii, iii
    - upperRoman: I, II, III
    - lowerLetter: a, b, c
    - decimalEnclosedCircle: ①, ②, ③
    """
```

需要实现的映射表：
- `decimal` / `decimalZero`: `str(number)`
- `lowerRoman`: 1→i, 2→ii, ... (使用自建映射或 roman 库)
- `upperRoman`: 1→I, 2→II, ...
- `lowerLetter`: 1→a, 2→b, ... (26 进制)
- `upperLetter`: 1→A, 2→B, ...
- `chineseCounting` / `chineseCountingThousand` / `chineseLegal`: 1→一, 2→二, ... (自建映射)
- `ideographDigital`: 1→一, 2→二, ...
- `decimalEnclosedCircle`: 1→①, 2→②, ... (Unicode 范围 ①-⑳)
- 其他格式: `str(number)`（降级）

**影响范围**: title 块的 `content` 将包含完整编号，下游 `is_numbered_style` 字段可帮助区分是否需要额外处理。

---

### P1-1: 下游渲染支持多格式编号（缺陷 #3）

#### 3a. list 块数据结构扩展

**目标文件**: `MinerU/mineru/model/docx/docx_converter.py`

**修改位置**: `_add_list_item` 方法中 list_block 创建处（L2500-L2505 等）

**变更内容**:

在 list_block 中增加 `numFmt` 字段：

```python
list_block = {
    "type": BlockType.LIST,
    "attribute": list_attribute,
    "content": [],
    "ilevel": ilevel,
    "numFmt": self._get_numfmt(numid, ilevel),  # 新增
}
```

新增辅助方法 `_get_numfmt`：

```python
def _get_numfmt(self, numId: int, ilvl: int) -> str:
    """获取 (numId, ilvl) 的 numFmt 值。"""
    lvl_element = self._get_numbering_level_definition(numId, ilvl)
    if lvl_element is None:
        return "decimal"
    namespaces = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    num_fmt_element = lvl_element.find(".//w:numFmt", namespaces=namespaces)
    if num_fmt_element is None:
        return "decimal"
    return num_fmt_element.get(
        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val",
        "decimal",
    )
```

#### 3b. 下游改用 numFmt 格式化编号

**目标文件**: `MinerU/mineru/backend/office/mkcontent/output_builders.py`

**修改位置**: `_flatten_list_items` 和 `_flatten_list_items_v2`

**变更内容**:

将 `_flatten_list_items` 中的：
```python
items.append(f"{indent}{ordered_counter}. {item_text}")
```
改为：
```python
numfmt = list_block.get('numFmt', 'decimal')
prefix = format_ordered_number(ordered_counter, numfmt)
items.append(f"{indent}{prefix}. {item_text}")
```

新增 `format_ordered_number` 函数（与 `_format_number_by_numfmt` 共享逻辑，可直接复用或内联）：

```python
def format_ordered_number(number: int, numfmt: str) -> str:
    """根据 numfmt 格式化有序列表编号。"""
    # 与 _format_number_by_numfmt 共享实现
```

**注意**: `_format_number_by_numfmt` 和 `format_ordered_number` 应共享同一套编号格式化逻辑，避免重复实现。建议将格式化逻辑提取到公共模块或通过继承复用。

---

### P1-2: 添加单元测试（缺陷 #8）

**目标文件**: 新建 `MinerU/tests/unittest/test_numbering.py`

**测试内容**:

1. `_is_numbered_list` 测试
   - `decimal` → True
   - `chineseCounting` → True
   - `bullet` → False
   - `None` (no numFmt) → False

2. `_advance_list_counter` 测试
   - 首次调用返回起始值
   - 后续调用递增
   - 子级重置（父级前进后子级计数器删除）

3. `_detect_heading_list_numids` 测试
   - 多级列表+正文穿插 → 被识别
   - 单级列表+正文穿插 → 不被识别
   - 多级列表无正文穿插 → 不被识别

4. `_add_list_item` 测试
   - 新列表创建
   - 增加缩进（子列表）
   - 减少缩进（关闭子列表）
   - 同级列表项

5. `_get_numbering_level_start` 测试
   - 默认值 1
   - abstractNum 级别 start
   - lvlOverride startOverride 覆盖

6. `_render_numbering_prefix` 测试（新增方法）
   - `chineseCounting` + `%1、` → "一、"
   - `decimal` + `(%1)` → "(1)"
   - `lowerRoman` + `%1.` → "i."

**测试策略**:
- 使用 `pytest` + `unittest.mock.patch` 模拟 XML 解析结果
- 对 `_is_numbered_list` 等纯逻辑方法可直接构造 mock lvl_element
- 对涉及状态的方法需构造 mock `DocxConverter` 实例并设置初始状态

---

### P2-1: 放宽 `_detect_heading_list_numids` 条件2（缺陷 #4）

**目标文件**: `MinerU/mineru/model/docx/docx_converter.py`

**修改位置**: `_detect_heading_list_numids` 末尾过滤（当前 L2753-L2758）

**变更内容**:

将条件2从"必须有 >1 种 ilevel"改为"允许单级列表通过检测，但增加正文密度阈值过滤"：

```python
# 方案 A（推荐）：允许单级标题列表，但要求较强的正文穿插证据
heading_numids = {
    nid for nid in heading_numids
    if len(numid_ilvels.get(nid, set())) > 1
    or _has_strong_content_interleaving(nid, items)  # 新增：检测穿插密度
}
```

其中 `_has_strong_content_interleaving` 检查该 numId 的列表项间穿插的正文段落数量是否超过阈值（如 ≥2）。

**权衡说明**:
- 放宽条件会增加将普通多段内容条目列表误判为标题列表的风险
- 通过增加"正文穿插密度"阈值来平衡：单级列表需要更多正文穿插证据才能被认定为标题列表
- 具体阈值需通过实际文档测试确定（建议初始设为 ≥2 个正文段落）

---

### P3-1: `_get_numbering_level_definition` 支持 lvlOverride 完整覆盖（缺陷 #5）

**目标文件**: `MinerU/mineru/model/docx/docx_converter.py`

**修改位置**: `_get_numbering_level_definition`（当前 L2364-L2386）

**变更内容**:

在查找 `<w:lvl>` 时，优先检查 `<w:num>` 中 `<w:lvlOverride>` 是否包含完整 `<w:lvl>` 覆盖：

```python
def _get_numbering_level_definition(self, numId: int, ilvl: int) -> Optional[BaseOxmlElement]:
    cache_key = (numId, ilvl)
    if cache_key in self._numbering_level_cache:
        return self._numbering_level_cache[cache_key]

    numbering_root = self._get_numbering_root()
    namespaces = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    lvl_element: Optional[BaseOxmlElement] = None

    # 1. 优先检查 num 的 lvlOverride 中是否有完整 lvl 覆盖
    num_element = self._get_numbering_num_element(numId)
    if num_element is not None:
        override_lvl = num_element.find(
            f"w:lvlOverride[@w:ilvl='{ilvl}']/w:lvl",
            namespaces=namespaces,
        )
        if override_lvl is not None:
            lvl_element = override_lvl

    # 2. 回退到 abstractNum 查找
    if lvl_element is None:
        abstract_num_element = self._get_abstract_numbering_element(numId)
        if numbering_root is not None and abstract_num_element is not None:
            lvl_xpath = f".//w:lvl[@w:ilvl='{ilvl}']"
            lvl_element = abstract_num_element.find(lvl_xpath, namespaces=namespaces)

    self._numbering_level_cache[cache_key] = lvl_element
    return lvl_element
```

---

### P3-2: 改进 `_add_list_item` 减少缩进时空栈回退（缺陷 #6）

**目标文件**: `MinerU/mineru/model/docx/docx_converter.py`

**修改位置**: `_add_list_item` 情况3 的栈空分支（当前 L2628-L2642）

**变更内容**:

当前行为：栈为空时直接创建新的顶层列表块，导致原列表被拆分。

改进方案：尝试查找 `cur_page` 中上一个属于同一 numId 的列表块并将其作为父块，而不是创建新块：

```python
if not self.list_block_stack:
    # 尝试在 cur_page 中查找属于同一 numId 的最近父列表块
    parent_block = self._find_parent_list_block(numid, ilevel)
    if parent_block is not None:
        list_item = {"type": BlockType.TEXT, "content": content_text}
        parent_block["content"].append(list_item)
        self.list_block_stack.append(parent_block)
        self.pre_ilevel = ilevel
        return None
    # 回退：创建新顶层列表
    ...
```

新增辅助方法 `_find_parent_list_block`：

```python
def _find_parent_list_block(self, numid: int, ilevel: int) -> Optional[dict]:
    """在 cur_page 中倒序查找属于同一 numId 且 ilevel <= 当前 ilevel 的列表块。"""
    for block in reversed(self.cur_page):
        if block.get("type") == BlockType.LIST and block.get("_numId") == numid:
            if block.get("ilevel", 0) <= ilevel:
                return block
    return None
```

**注意**: 需要在 list_block 中存储 `_numId` 内部字段用于回溯查找（以 `_` 开头表示内部使用，不对外暴露）。

---

### P3-3: `_close_active_list` 支持可选计数器重置（缺陷 #7）

**目标文件**: `MinerU/mineru/model/docx/docx_converter.py`

**修改位置**: `_close_active_list`（当前 L792-L796）和调用处

**变更内容**:

保留默认行为（不重置计数器），增加可选参数：

```python
def _close_active_list(self, reset_counters: bool = False) -> None:
    """关闭当前活跃列表块。

    Args:
        reset_counters: 是否同时重置编号计数器。
            默认 False（保留 Word numId 的连续编号计数）。
            设为 True 时同步清空 list_counters。
    """
    self.pre_num_id = -1
    self.pre_ilevel = -1
    self.list_block_stack = []
    if reset_counters:
        self.list_counters = {}
```

对于表格、TOC 等明确的中断场景，调用 `_close_active_list(reset_counters=True)`，使编号在中断后重新开始。

---

## 文件修改清单

| 文件 | 修改内容 | 优先级 |
|------|---------|--------|
| `MinerU/mineru/model/docx/docx_converter.py` | #1: 新增 `_render_numbering_prefix`、`_format_number_by_numfmt`；修改 heading 列表处理分支 | P0 |
| `MinerU/mineru/model/docx/docx_converter.py` | #2: 扩充 `numbered_formats` 集合 | P0 |
| `MinerU/mineru/model/docx/docx_converter.py` | #3a: list_block 增加 `numFmt` 字段、新增 `_get_numfmt` | P1 |
| `MinerU/mineru/backend/office/mkcontent/output_builders.py` | #3b: 新增 `format_ordered_number`、修改 `_flatten_list_items`/`_flatten_list_items_v2` | P1 |
| `MinerU/tests/unittest/test_numbering.py` (新建) | #8: 单元测试覆盖 | P1 |
| `MinerU/mineru/model/docx/docx_converter.py` | #4: 放宽 `_detect_heading_list_numids` 条件2 | P2 |
| `MinerU/mineru/model/docx/docx_converter.py` | #5: `_get_numbering_level_definition` 支持 lvlOverride lvl 覆盖 | P3 |
| `MinerU/mineru/model/docx/docx_converter.py` | #6: `_add_list_item` 空栈回退策略改进 | P3 |
| `MinerU/mineru/model/docx/docx_converter.py` | #7: `_close_active_list` 增加可选重置 | P3 |

---

## 实施建议

1. **分阶段实施**：建议按 P0 → P1 → P2 → P3 的顺序逐步提交，每个优先级独立 MR/PR
2. **P0 先行**：#2（扩充 format 集合）改动最小、风险最低，可先上线
3. **编号格式化函数复用**：#1 和 #3 都需要编号格式化功能，建议将 `_format_number_by_numfmt`（或共享版本 `format_ordered_number`）放在公共位置，避免重复实现
4. **测试先行**：在修改 #1/#2 前，先为 `_is_numbered_list` 等现有方法添加测试作为回归基线
5. **测试文档**：创建包含各种编号格式（中文、罗马、字母等）的测试 DOCX 文件，用于端到端验证
6. **兼容性**：所有修改需确保向后兼容——旧版 middle_json 缺少 `numFmt` 字段时，下游应有默认值兜底 (`"decimal"`)
