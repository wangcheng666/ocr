import requests, json

# Test only chart PDF, show full response
print("=" * 60)
print("CHART PDF - Full response:")
print("=" * 60)
with open("tests/data/pdf/图表测试文件.pdf", "rb") as f:
    resp = requests.post("http://localhost:8000/parse", params={"engine": "vlm"}, files={"file": f})
data = resp.json()
print("status:", data.get("status"))
print("engine:", data.get("engine"))
print("page_count:", data.get("page_count"))
md = data.get("content", "")
print("content length:", len(md))
print()
print("--- CONTENT ---")
print(md[:2000])
print("--- END ---")
