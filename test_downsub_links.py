import requests

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Origin": "https://downsub.com",
    "Referer": "https://downsub.com/"
}

test_id = "dQw4w9WgXcQ"
formats = ["txt", "srt", "vtt"]
langs = ["en", "bn", "hi"]

for fmt in formats:
    for lang in langs:
        url = f"https://subtitle.downsub.com/{fmt}/youtube/{test_id}/{lang}"
        res = requests.get(url, headers=headers)
        print(f"URL: {url} -> Status: {res.status_code}, Length: {len(res.text)}")
        if res.status_code == 200 and len(res.text) > 20:
            print("SAMPLE CONTENT:")
            print(res.text[:300])
            print("=" * 50)
