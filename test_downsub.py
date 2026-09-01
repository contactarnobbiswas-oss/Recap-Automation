import requests
from urllib.parse import quote

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Origin": "https://downsub.com",
    "Referer": "https://downsub.com/"
}

video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
encoded_url = quote(video_url, safe='')

# Test variations
for endpoint in [
    f"https://get-info.downsub.com/?url={encoded_url}",
    f"https://get-info.downsub.com/?url={video_url}",
    f"https://subtitle.downsub.com/?url={encoded_url}",
]:
    res = requests.get(endpoint, headers=headers)
    print(f"Endpoint: {endpoint}")
    print("Status:", res.status_code)
    print("Text:", res.text[:500])
    print("-" * 40)
