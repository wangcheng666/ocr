"""验证 image_path 是否已加上 cut_images/ 前缀"""
import requests, json, zipfile, io
session = requests.Session()
session.trust_env = False

with open("tests/data/pdf/图表测试文件.pdf", "rb") as f:
    r = session.post(
        "http://localhost:8000/parse",
        files={"file": f},
        data={"engine": "vlm", "f_dump_md": "true", "f_dump_middle_json": "true"},
        timeout=120,
    )
d = r.json()
print(f"status={d['status']} pages={d.get('page_count')}")

url = d["download_url"]
resp = session.get(url)
z = zipfile.ZipFile(io.BytesIO(resp.content))

# 查找 middle.json
for n in z.namelist():
    if n.endswith("_middle.json"):
        mj = json.load(z.open(n))
        # 遍历所有 image_path
        found = []

        def walk(obj):
            if isinstance(obj, dict):
                if "image_path" in obj and obj["image_path"]:
                    found.append(obj["image_path"])
                for v in obj.values():
                    walk(v)
            elif isinstance(obj, list):
                for item in obj:
                    walk(item)

        walk(mj)
        print(f"\nFound {len(found)} image_path entries:")
        for p in found:
            print(f"  {p}")
        print()

        # 验证所有路径都以 cut_images/ 开头
        all_ok = all(p.startswith("cut_images/") for p in found)
        if all_ok:
            print("✅ All image_path entries have cut_images/ prefix")
        else:
            bad = [p for p in found if not p.startswith("cut_images/")]
            print(f"❌ {len(bad)} entries missing cut_images/ prefix: {bad}")
        break
