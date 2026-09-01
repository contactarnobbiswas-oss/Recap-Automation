import requests
import base64
from urllib.parse import quote

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Origin": "https://downsub.com",
    "Referer": "https://downsub.com/"
}

yt_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
b64_url = base64.b64encode(yt_url.encode('utf-8')).decode('utf-8')
quoted_url = quote(yt_url, safe='')

for path_val in [b64_url, quoted_url, yt_url]:
    p = f"https://get-info.downsub.com/{path_val}"
    res = requests.get(p, headers=headers)
    print(f"Path: {p[:60]}... Status {res.status_code}: {res.text[:300]}")
