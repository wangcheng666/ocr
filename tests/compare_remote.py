"""比较 remote_middle.json vs 图表测试文件_middle.json"""
import json
from collections import Counter

f1 = '/home/czce/Documents/code/python/ocr/tests/results/pdf/remote_middle.json'
f2 = '/home/czce/Documents/code/python/ocr/tests/results/pdf/图表测试文件_middle.json'

with open(f1) as f:
    a = json.load(f)
with open(f2) as f:
    b = json.load(f)

print('=== 文档基本信息 ===')
print(f'remote   backend={a["_backend"]}, version={a["_version_name"]}, pages={len(a["pdf_info"])}')
print(f'本地      backend={b["_backend"]}, version={b["_version_name"]}, pages={len(b["pdf_info"])}')

diff_count = 0
for i in range(max(len(a['pdf_info']), len(b['pdf_info']))):
    if i >= len(a['pdf_info']):
        print(f'\n第{i}页: remote 无此页')
        continue
    if i >= len(b['pdf_info']):
        print(f'\n第{i}页: 本地无此页')
        continue

    ap = a['pdf_info'][i]
    bp = b['pdf_info'][i]
    ab = ap.get('para_blocks', [])
    bb = bp.get('para_blocks', [])
    
    print(f'\n--- 第 {i} 页 (remote={len(ab)}块, 本地={len(bb)}块) ---')

    for j in range(max(len(ab), len(bb))):
        if j >= len(ab):
            print(f'  remote缺少块[{j}]: 本地type={bb[j].get("type")}')
            diff_count += 1
            continue
        if j >= len(bb):
            print(f'  本地缺少块[{j}]: remotetype={ab[j].get("type")}')
            diff_count += 1
            continue

        ba = ab[j]
        bbk = bb[j]
        ta, tb = ba.get('type'), bbk.get('type')

        if ta != tb:
            print(f'  块[{j}] type不同: remote={ta} vs 本地={tb}')
            diff_count += 1
            continue

        # 对比文本内容
        def get_spans(block):
            for line in block.get('lines', []):
                for span in line.get('spans', []):
                    yield span

        spans_a = list(get_spans(ba))
        spans_b = list(get_spans(bbk))

        if len(spans_a) != len(spans_b):
            print(f'  块[{j}] ({ta}) span数量: remote={len(spans_a)} vs 本地={len(spans_b)}')
            diff_count += 1
            continue

        for si, (sa, sb) in enumerate(zip(spans_a, spans_b)):
            diffs = []
            for key in set(list(sa.keys()) + list(sb.keys())):
                va = sa.get(key)
                vb = sb.get(key)
                if key == 'content':
                    if va != vb:
                        min_len = min(len(va or ''), len(vb or ''))
                        pos = next((p for p in range(min_len) if (va or '')[p] != (vb or '')[p]), min_len)
                        a_snip = repr((va or '')[max(0,pos-15):pos+15])
                        b_snip = repr((vb or '')[max(0,pos-15):pos+15])
                        diffs.append(f'content差异@位置{pos}: {a_snip} vs {b_snip}')
                elif key == 'type':
                    if va != vb:
                        diffs.append(f'type: {va} vs {vb}')
                elif key == 'image_path':
                    if va != vb:
                        diffs.append(f'image_path: ...{va[-20:] if va else None} vs ...{vb[-20:] if vb else None}')
            if diffs:
                print(f'  块[{j}] ({ta}) span[{si}] 差异:')
                for d in diffs:
                    print(f'    {d}')
                diff_count += 1

print(f'\n{"="*40}')
print(f'总计差异数: {diff_count}')
if diff_count == 0:
    print('两个文件完全一致 ✅')
