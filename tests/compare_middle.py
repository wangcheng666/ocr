"""比较两个 OCR 中间结果的差异"""
import json, sys

f1 = '/home/czce/Documents/code/python/ocr/tests/results/pdf/图表测试文件_middle.json'
f2 = '/home/czce/Documents/code/python/ocr/tests/results/pdf/custom_middle.json'

with open(f1) as f:
    a = json.load(f)
with open(f2) as f:
    b = json.load(f)

print('=== 顶层字段 ===')
print(f'A keys: {set(a.keys())}')
print(f'B keys: {set(b.keys())}')

print(f'\n=== _backend ===')
print(f'A: {a.get("_backend")}')
print(f'B: {b.get("_backend")}')

print(f'\n=== 页数 ===')
pa = a.get('pdf_info', [])
pb = b.get('pdf_info', [])
print(f'A: {len(pa)} 页')
print(f'B: {len(pb)} 页')

for i in range(min(len(pa), len(pb))):
    ap = pa[i]
    bp = pb[i]
    ab = ap.get('para_blocks', [])
    bb = bp.get('para_blocks', [])
    
    print(f'\n--- 第 {i} 页 ---')
    print(f'A 块数: {len(ab)}, B 块数: {len(bb)}')
    
    # 比较块类型分布
    from collections import Counter
    atypes = Counter(b.get('type') for b in ab)
    btypes = Counter(b.get('type') for b in bb)
    print(f'A 类型: {dict(atypes)}')
    print(f'B 类型: {dict(btypes)}')
    
    # 对比每块的内容长度
    for j in range(max(len(ab), len(bb))):
        if j >= len(ab):
            print(f'  A 缺少块[{j}]: type={bb[j].get("type")}')
            continue
        if j >= len(bb):
            print(f'  B 缺少块[{j}]: type={ab[j].get("type")}')
            continue
        
        at = ab[j].get('type')
        bt = bb[j].get('type')
        
        if at != bt:
            print(f'  块[{j}] 类型不同: A={at} vs B={bt}')
            continue
        
        # 比较文本内容
        def get_text(block):
            texts = []
            for line in block.get('lines', []):
                for span in line.get('spans', []):
                    texts.append(span.get('content', ''))
            return ''.join(texts)
        
        atext = get_text(ab[j])
        btext = get_text(bb[j])
        
        if atext != btext:
            # 显示差异
            alen = len(atext)
            blen = len(btext)
            diff_pos = next((k for k in range(min(alen, blen)) if atext[k] != btext[k]), min(alen, blen))
            print(f'  块[{j}] ({at}) 内容不同: A_len={alen} B_len={blen} 首异位置={diff_pos}')
            print(f'    A: {atext[max(0,diff_pos-20):diff_pos+20]}')
            print(f'    B: {btext[max(0,diff_pos-20):diff_pos+20]}')
        elif ab[j].get('type') in ('image', 'table', 'chart'):
            # 对比图片/表格元数据
            aimg = [s.get('image_path','') for b2 in ab[j].get('blocks',[]) for l in b2.get('lines',[]) for s in l.get('spans',[]) if s.get('type')=='image']
            bimg = [s.get('image_path','') for b2 in bb[j].get('blocks',[]) for l in b2.get('lines',[]) for s in l.get('spans',[]) if s.get('type')=='image']
            if aimg != bimg:
                print(f'  块[{j}] ({at}) 图片路径不同: A={aimg} B={bimg}')
