import requests
import re

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

js_url = "https://downsub.com/js/main.f3ab96ad4eb8c169687a.js"
resp = requests.get(js_url, headers=headers)

matches = re.findall(r'.{0,150}getDataYTB.{0,150}', resp.text)
for m in matches[:10]:
    print("getDataYTB Context:", m)
    print("-" * 60)
