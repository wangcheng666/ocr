"""验证 LLM 标题优化是否生效"""
import json, requests, zipfile, io

BASE = 'http://localhost:8000'
FILE = 'tests/data/pdf/图表测试文件.pdf'

with open(FILE, 'rb') as f:
    r = requests.post(f'{BASE}/parse', files={'file': f},
                      data={'engine': 'vlm', 'f_dump_md': 'true'},
                      timeout=120)

d = r.json()
print(f'status={d["status"]}  pages={d["page_count"]}  clen={len(d["content"])}')

# 从 ZIP 中读取 middle_json
resp = requests.get(d['download_url'])
z = zipfile.ZipFile(io.BytesIO(resp.content))
for name in z.namelist():
    if name.endswith('_middle.json'):
        mj = json.load(z.open(name))
        found = False
        for page in mj.get('pdf_info', []):
            for blk in page.get('para_blocks', []):
                if blk.get('type') == 'title':
                    has_level = 'level' in blk
                    print(f'title: level={blk.get("level", "N/A")}  has_level={has_level}')
                    found = True
                    break
            if found:
                break
        break
