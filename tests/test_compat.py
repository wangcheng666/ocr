"""兼容性测试 — 验证所有引擎类型都能正常解析"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.chdir(os.path.join(os.path.dirname(__file__), '..'))

import requests

BASE = 'http://localhost:8000'
tests = [
    # (label, path, engine)
    ('VLM + PDF',  'tests/data/pdf/test_demo.pdf', 'vlm'),
    ('Office + docx', 'tests/data/docx/docx_01.docx', 'office'),
    ('Office + pptx', 'tests/data/pptx/pptx_01.pptx', 'office'),
    ('Office + xlsx', 'tests/data/xlsx/xlsx_01.xlsx', 'office'),
    ('Hybrid + PDF', 'tests/data/pdf/test_demo.pdf', 'hybrid'),
]

all_ok = True
for label, path, engine in tests:
    print(f'--- {label} ---')
    with open(path, 'rb') as f:
        files = {'file': f}
        data = {
            'engine': engine,
            'f_dump_md': 'false',
            'f_dump_content_list': 'false',
            'f_dump_middle_json': 'false',
            'f_dump_model_output': 'false',
            'f_dump_full_page_images': 'false',
        }
        try:
            timeout = 600 if engine == 'hybrid' else 120
            r = requests.post(f'{BASE}/parse', files=files, data=data, timeout=timeout)
        except requests.Timeout:
            print(f'  ⏰ TIMEOUT (>{timeout}s)')
            all_ok = False
            continue
        except requests.ConnectionError:
            print(f'  💥 Connection refused')
            all_ok = False
            continue

    d = r.json()
    if r.status_code == 200 and d.get('status') == 'success':
        content_len = len(d.get('content', ''))
        print(f'  ✅ status=success, pages={d.get("page_count")}, content_len={content_len}')
    else:
        print(f'  ❌ code={r.status_code}, detail={d.get("detail", d)}')
        all_ok = False
    print()

if all_ok:
    print('🎉 所有引擎类型均正常!')
else:
    print('💥 部分测试失败')
    sys.exit(1)
