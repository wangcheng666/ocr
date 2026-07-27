"""测试 Office 文件类型 (docx/pptx/xlsx)"""

import sys
import os
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.chdir(os.path.join(os.path.dirname(__file__), '..'))

import requests

BASE = 'http://localhost:8000'
tests = [
    ('docx', 'tests/data/docx/docx_01.docx', 'office'),
    ('pptx', 'tests/data/pptx/pptx_01.pptx', 'office'),
    ('xlsx', 'tests/data/xlsx/xlsx_01.xlsx', 'office'),
]

for name, path, engine in tests:
    print(f'--- Testing {name} ---')
    with open(path, 'rb') as f:
        t0 = time.time()
        r = requests.post(f'{BASE}/parse', files={'file': f},
            data={'engine': engine, 'f_dump_md': 'false', 'f_dump_full_page_images': 'false'},
            timeout=120)
        elapsed = time.time() - t0
    d = r.json()
    print(f'  status={d.get("status")}, code={r.status_code}')
    if r.status_code == 200:
        print(f'  pages={d.get("page_count")}, content_len={len(d.get("content",""))}')
        print(f'  file_type={d.get("file_type")}')
        print(f'  time={elapsed:.2f}s')
    else:
        print(f'  error={d.get("detail","")}')
    print()
