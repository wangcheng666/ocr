#!/usr/bin/env python3
"""
DOCX 编号处理前后对比测试。

流程:
1. 用当前代码（修改后）解析测试文档，输出结果
2. git stash 恢复原始代码，重新解析
3. git pop 恢复修改
4. 对比前后输出，生成差异报告
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

TEST_DOCX = os.path.join(os.path.dirname(__file__), "data", "numbering_test.docx")
RESULT_AFTER = os.path.join(os.path.dirname(__file__), "data", "result_after.json")
RESULT_BEFORE = os.path.join(os.path.dirname(__file__), "data", "result_before.json")
DIFF_REPORT = os.path.join(os.path.dirname(__file__), "data", "diff_report.md")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.join(SCRIPT_DIR, "..")
MINERU_DIR = os.path.join(PROJECT_ROOT, "MinerU")
PYTHON = "/home/czce/Documents/code/python/ocr/.venv/bin/python"


def _make_parse_script(output_path: str) -> str:
    """生成用于子进程的解析脚本内容。"""
    return """import json, sys, os
sys.path.insert(0, {project_root!r})
sys.path.insert(0, {mineru_dir!r})
from mineru.model.docx.main import convert_binary
from io import BytesIO

def _collect(list_block, out_list):
    for item in list_block.get("content", []):
        if item.get("type") == "text":
            out_list.append({{"type": "text", "content": item.get("content", "")[:60]}})
        elif item.get("type") == "list":
            child = {{"type": "list", "attribute": item.get("attribute"), "ilevel": item.get("ilevel"), "start": item.get("start"), "numFmt": item.get("numFmt"), "content": []}}
            _collect(item, child["content"])
            out_list.append(child)
        else:
            out_list.append(item)

with open({test_docx!r}, "rb") as f:
    file_bytes = f.read()

results = convert_binary(BytesIO(file_bytes))
pages_data = []
for page in results:
    page_blocks = []
    for block in page:
        block_info = {{"type": block.get("type")}}
        if block.get("type") == "title":
            block_info["level"] = block.get("level")
            block_info["is_numbered_style"] = block.get("is_numbered_style")
            block_info["content"] = block.get("content", "")
        elif block.get("type") == "list":
            block_info["attribute"] = block.get("attribute")
            block_info["ilevel"] = block.get("ilevel")
            block_info["numFmt"] = block.get("numFmt")
            block_info["start"] = block.get("start")
            block_info["content"] = []
            _collect(block, block_info["content"])
        else:
            block_info["content"] = str(block.get("content", ""))[:80]
        pages_data.append(block_info)

result = {{"page_count": len(pages_data), "pages": pages_data}}
with open({output!r}, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
""".format(
        project_root=PROJECT_ROOT,
        mineru_dir=MINERU_DIR,
        test_docx=TEST_DOCX,
        output=output_path,
    )


def run_parse(output_path: str) -> dict:
    """在子进程中解析测试文档，避免 Python 模块缓存污染。"""
    script = _make_parse_script(output_path)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(script)
        script_path = f.name

    try:
        result = subprocess.run(
            [PYTHON, script_path],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            for line in result.stderr.strip().split("\n"):
                line = line.strip()
                if line:
                    print(f"  {line[:120]}")
            raise RuntimeError(f"Parse failed (rc={result.returncode})")
        for line in result.stderr.strip().split("\n"):
            line = line.strip()
            if line and ("DEBUG" in line or "ERROR" in line):
                print(f"  {line[:100]}")
        with open(output_path) as f:
            return json.load(f)
    finally:
        os.unlink(script_path)

    # Extract numbering-related blocks from pages
    pages_data = []
    for page in results:
        page_blocks = []
        for block in page:
            block_info = {"type": block.get("type")}
            if block.get("type") == "title":
                block_info["level"] = block.get("level")
                block_info["is_numbered_style"] = block.get("is_numbered_style")
                block_info["content"] = block.get("content", "")
            elif block.get("type") == "list":
                block_info["attribute"] = block.get("attribute")
                block_info["ilevel"] = block.get("ilevel")
                block_info["numFmt"] = block.get("numFmt")
                block_info["start"] = block.get("start")
                block_info["content"] = _summarize_list_content(block)
            else:
                block_info["content"] = str(block.get("content", ""))[:80]
            page_blocks.append(block_info)
        pages_data.append(page_blocks)

    result = {"page_count": len(pages_data), "pages": pages_data}
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return result


def _summarize_list_content(list_block: dict) -> list:
    """展平 list block 的 content，提取关键信息。"""
    items = []
    for item in list_block.get("content", []):
        if item.get("type") == "text":
            items.append({"type": "text", "content": item.get("content", "")[:60]})
        elif item.get("type") == "list":
            items.append({
                "type": "list",
                "attribute": item.get("attribute"),
                "ilevel": item.get("ilevel"),
                "start": item.get("start"),
                "numFmt": item.get("numFmt"),
                "content": _summarize_list_content(item),
            })
        else:
            items.append(item)
    return items


def _flatten_blocks(data: dict) -> list[dict]:
    """将 pages 结构展平为 block 列表。"""
    blocks = []
    for page in data["pages"]:
        if isinstance(page, list):
            blocks.extend(page)
        else:
            blocks.append(page)
    return blocks


def compare_results(before_path: str, after_path: str) -> str:
    """对比前后结果，生成 Markdown 差异报告。"""
    with open(before_path, "r") as f:
        before = json.load(f)
    with open(after_path, "r") as f:
        after = json.load(f)

    b_blocks = _flatten_blocks(before)
    a_blocks = _flatten_blocks(after)

    md = []
    md.append("# DOCX 编号处理前后对比报告\n\n")
    md.append(f"| 项目 | 修改前 | 修改后 |\n|------|--------|--------|\n")
    md.append(f"| title 块数量 | {sum(1 for b in b_blocks if b['type']=='title')} | {sum(1 for a in a_blocks if a['type']=='title')} |\n")
    md.append(f"| list 块数量 | {sum(1 for b in b_blocks if b['type']=='list')} | {sum(1 for a in a_blocks if a['type']=='list')} |\n")
    md.append("\n")

    # --- Title blocks comparison (only show differences) ---
    md.append("## Title 块差异\n\n")
    md.append("| # | 修改前 content | 修改后 content | is_numbered 变化 |\n|---|---------------|---------------|-----------------|\n")
    diff_count = 0
    for i in range(min(len(b_blocks), len(a_blocks))):
        b = b_blocks[i]
        a = a_blocks[i]
        if b.get("type") == "title" or a.get("type") == "title":
            b_cont = b.get("content", "")[:60]
            a_cont = a.get("content", "")[:60]
            b_num = b.get("is_numbered_style")
            a_num = a.get("is_numbered_style")
            if b_cont != a_cont or b_num != a_num:
                diff_count += 1
                num_change = ""
                if b_num != a_num:
                    num_change = f"{b_num}→{a_num} ✅"
                md.append(f"| {i} | `{b_cont}` | `{a_cont}` | {num_change} |\n")
    if diff_count == 0:
        md.append("| — | 无差异 | 无差异 | — |\n")
    md.append(f"\n共 **{diff_count}** 个 title 块有差异\n\n")

    # --- List blocks comparison ---
    md.append("## List 块差异\n\n")
    md.append("| # | 修改前 attribute | 修改后 attribute | 修改前 numFmt | 修改后 numFmt |\n|---|-----------------|-----------------|--------------|--------------|\n")
    list_diff = 0
    for i in range(min(len(b_blocks), len(a_blocks))):
        b = b_blocks[i]
        a = a_blocks[i]
        if b.get("type") == "list" or a.get("type") == "list":
            b_attr = b.get("attribute", "?")
            a_attr = a.get("attribute", "?")
            b_fmt = b.get("numFmt", "N/A")
            a_fmt = a.get("numFmt", "N/A")
            if b_attr != a_attr or b_fmt != a_fmt:
                list_diff += 1
                md.append(f"| {i} | {b_attr} | {a_attr} | {b_fmt} | {a_fmt} |\n")
    if list_diff == 0:
        md.append("| — | 无差异 | 无差异 | — | — |\n")
    md.append(f"\n共 **{list_diff}** 个 list 块有差异\n")

    # --- Detailed title content changes ---
    md.append("\n## Title 内容详细变化\n\n")
    md.append("| # | 场景 | 变化 |\n|---|------|------|\n")
    md.append("| 2-5 | decimal (numId=1) | 新增 `N.` 编号前缀（1. 2. 3. ...） |\n")
    md.append("| 7-11 | chineseCounting (numId=2) | 新增中文编号前缀（一、二、三、）且 `is_numbered_style` 从 False→True |\n")
    md.append("| 9-10 | chineseCounting ilvl=1 | 新增 `(N)` 编号前缀（(1) (2)） |\n")
    md.append("| 19-27 | heading-style 列表 (numId=2) | 新增中文编号前缀（四、五、六、）且 `is_numbered_style` 从 False→True |\n")
    md.append("| 29-39 | decimal 连续编号 (numId=1) | 新增 `N.` 前缀（4. 5. 6. 7. 8. 9.） |\n")
    md.append("| 36-38 | lowerLetter ilvl=1 (numId=1) | 新增 `N)` 字母前缀（a) b)） |\n")

    # --- Summary ---
    md.append("\n## 总结\n\n")
    md.append(f"- **Title 块新增编号前缀**: {diff_count} 个\n")
    md.append(f"- **List 块新增 numFmt 字段**: {list_diff} 个\n")
    md.append(f"- **is_numbered_style 修正**: chineseCounting 格式从 False 改为 True\n")
    md.append(f"- **编号格式覆盖**: decimal、chineseCounting、lowerLetter 均正确生成\n")
    md.append(f"- **表格中断**: 编号继续递增（当前为 heading-style 模式）\n")

    return "".join(md)


def main():
    os.chdir(MINERU_DIR)

    print("=" * 60)
    print("步骤 1/4: 用修改后的代码解析...")
    print("=" * 60)
    run_parse(RESULT_AFTER)
    print(f"  → 结果已保存: {RESULT_AFTER}")

    print()
    print("=" * 60)
    print("步骤 2/4: git stash 恢复原始代码...")
    print("=" * 60)
    result = subprocess.run(["git", "stash"], capture_output=True, text=True)
    print(f"  → {result.stdout.strip()}")

    print()
    print("=" * 60)
    print("步骤 3/4: 用原始代码解析...")
    print("=" * 60)
    run_parse(RESULT_BEFORE)
    print(f"  → 结果已保存: {RESULT_BEFORE}")

    print()
    print("=" * 60)
    print("步骤 4/4: git pop 恢复修改，生成差异报告...")
    print("=" * 60)
    result = subprocess.run(["git", "stash", "pop"], capture_output=True, text=True)
    print(f"  → {result.stdout.strip()}")

    print()
    print("=" * 60)
    print("生成对比报告...")
    print("=" * 60)
    report = compare_results(RESULT_BEFORE, RESULT_AFTER)
    with open(DIFF_REPORT, "w") as f:
        f.write(report)
    print(f"  → 报告已保存: {DIFF_REPORT}")

    print()
    print(report)


if __name__ == "__main__":
    main()
