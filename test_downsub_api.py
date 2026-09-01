import requests

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Origin": "https://downsub.com",
    "Referer": "https://downsub.com/",
    "Content-Type": "application/json"
}

yt_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# POST test
res_post = requests.post("https://get.downsub.com/", json={"url": yt_url}, headers=headers)
print("POST Status:", res_post.status_code)
print("POST Text:", res_post.text[:500])

# GET test with full encoded URL as path
res_get_path = requests.get(f"https://get.downsub.com/?url={yt_url}", headers=headers)
print("GET Params Status:", res_get_path.status_code)
print("GET Params Text:", res_get_path.text[:500])
