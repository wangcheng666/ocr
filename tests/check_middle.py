import requests, json, zipfile, io
session = requests.Session()
session.trust_env = False

with open('tests/data/pdf/图表测试文件.pdf','rb') as f:
    r = session.post('http://localhost:8000/parse', files={'file': f},
                     data={'engine':'vlm','f_dump_md':'true','f_dump_middle_json':'true'},
                     timeout=120)
d = r.json()
print(f'status={d["status"]} pages={d["page_count"]}')
url = d['download_url']
resp = session.get(url)
z = zipfile.ZipFile(io.BytesIO(resp.content))
for n in z.namelist():
    if n.endswith('_middle.json'):
        mj = json.load(z.open(n))
        for p in mj.get('pdf_info',[]):
            for b in p.get('para_blocks',[]):
                for blk in b.get('blocks',[]):
                    if blk.get('type')=='chart_body':
                        for line in blk.get('lines',[]):
                            for span in line.get('spans',[]):
                                if span.get('type')=='chart':
                                    print(f'chart content:\n{span["content"]}')
                                    break
        break
