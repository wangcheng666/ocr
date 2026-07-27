"""测试图表 PDF 并下载结果"""
import json, requests, sys

BASE = 'http://localhost:8000'
FILE = 'tests/data/pdf/图表测试文件.pdf'

with open(FILE, 'rb') as f:
    r = requests.post(f'{BASE}/parse', files={'file': f},
                      data={'engine': 'vlm', 'f_dump_md': 'true'},
                      timeout=120)

d = r.json()
print(f'status={d["status"]}  pages={d["page_count"]}  clen={len(d["content"])}')

# 下载 ZIP
url = d['download_url']
resp = requests.get(url)
out = 'tests/results/pdf/chart_output.zip'
with open(out, 'wb') as f:
    f.write(resp.content)
print(f'ZIP downloaded: {len(resp.content)} bytes -> {out}')
