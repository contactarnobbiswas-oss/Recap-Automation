import requests

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Content-Type": "application/json"
}

yt_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# Savesubs API test
try:
    res = requests.post("https://savesubs.com/action/extract", json={"data": {"url": yt_url}}, headers=headers, timeout=10)
    print("Savesubs status:", res.status_code)
    print("Savesubs response:", res.text[:500])
except Exception as e:
    print("Savesubs error:", e)
