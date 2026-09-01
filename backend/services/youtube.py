import os
import re
import json
import glob
import requests
import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi
from typing import Dict, Any, List

def extract_video_id(url: str) -> str:
    """
    Extracts the 11-character YouTube video ID from various YouTube URL formats.
    """
    regex = r'(?:v=|\/|youtu\.be\/|embed\/)([a-zA-Z0-9_-]{11})'
    match = re.search(regex, url)
    if match:
        return match.group(1)
    raise ValueError("Invalid YouTube URL provided.")


def get_video_metadata(url: str, output_dir: str) -> Dict[str, Any]:
    """
    Fetches video metadata (title, thumbnail URL, channel, duration)
    and downloads the MP4 video using yt-dlp.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': os.path.join(output_dir, '%(id)s.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        video_id = info.get('id', '')
        title = info.get('title', '')
        thumbnail = info.get('thumbnail', '')
        channel = info.get('uploader', '')
        duration = info.get('duration', 0)
        
        video_filename = f"{video_id}.mp4"
        video_filepath = os.path.join(output_dir, video_filename)

        return {
            "video_id": video_id,
            "title": title,
            "thumbnail_url": thumbnail,
            "channel": channel,
            "duration": duration,
            "video_path": video_filepath,
            "video_filename": video_filename
        }


def get_transcript_via_timedtext(video_id: str) -> str:
    """
    DownSub Direct Method: Fetches ytInitialPlayerResponse directly from YouTube video page
    and parses YouTube's internal timedtext API (fmt=json3).
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9"
        }
        url = f"https://www.youtube.com/watch?v={video_id}"
        resp = requests.get(url, headers=headers, timeout=10)
        
        if resp.status_code != 200:
            return ""

        # Extract ytInitialPlayerResponse JSON block
        match = re.search(r'ytInitialPlayerResponse\s*=\s*({.*?});', resp.text)
        if not match:
            return ""

        player_data = json.loads(match.group(1))
        caption_tracks = (
            player_data.get("captions", {})
            .get("playerCaptionsTracklistRenderer", {})
            .get("captionTracks", [])
        )

        if not caption_tracks:
            return ""

        # Prefer English/Bengali or pick first track
        selected_track = caption_tracks[0]
        for track in caption_tracks:
            lang_code = track.get("languageCode", "")
            if lang_code in ["en", "bn"]:
                selected_track = track
                break

        base_url = selected_track.get("baseUrl")
        if not base_url:
            return ""

        # Request json3 formatted timedtext
        caption_res = requests.get(base_url + "&fmt=json3", headers=headers, timeout=10)
        if caption_res.status_code != 200:
            return ""

        caption_json = caption_res.json()
        events = caption_json.get("events", [])
        
        lines = []
        for ev in events:
            segs = ev.get("segs", [])
            line_text = "".join([s.get("utf8", "") for s in segs]).strip()
            line_text = line_text.replace('\n', ' ')
            if line_text and line_text != "\n":
                lines.append(line_text)

        clean_script = " ".join(lines)
        # Clean repetitive whitespace
        clean_script = re.sub(r'\s+', ' ', clean_script).strip()
        return clean_script
    except Exception as e:
        print(f"Timedtext direct extraction failed: {e}")
        return ""


def get_transcript_via_ytdlp(url: str, output_dir: str) -> str:
    """
    Fallback Layer 3: Extract subtitles/auto-captions using yt-dlp.
    """
    try:
        sub_dir = os.path.join(output_dir, "subs")
        os.makedirs(sub_dir, exist_ok=True)
        
        ydl_opts = {
            'skip_download': True,
            'writeautosub': True,
            'writesubtitles': True,
            'subtitleslangs': ['en', 'bn', 'hi', 'es', 'fr', 'de', 'live_chat'],
            'subtitlesformat': 'vtt/ttml/srt/best',
            'outtmpl': os.path.join(sub_dir, '%(id)s'),
            'quiet': True,
            'no_warnings': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        sub_files = glob.glob(os.path.join(sub_dir, "*.*"))
        if not sub_files:
            return ""

        sub_file = sub_files[0]
        with open(sub_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        clean_lines = []
        for line in content.splitlines():
            line_str = line.strip()
            if not line_str or line_str.startswith('WEBVTT') or line_str.startswith('Kind:') or line_str.startswith('Language:'):
                continue
            if '-->' in line_str or line_str.isdigit():
                continue
            clean_text = re.sub(r'<[^>]+>', '', line_str).strip()
            if clean_text and (not clean_lines or clean_lines[-1] != clean_text):
                clean_lines.append(clean_text)

        for sf in sub_files:
            try:
                os.remove(sf)
            except Exception:
                pass

        return " ".join(clean_lines)
    except Exception as e:
        print(f"yt-dlp subtitle extraction fallback failed: {e}")
        return ""


def get_transcript(video_id: str, url: str = None, output_dir: str = ".") -> Dict[str, Any]:
    """
    Bulletproof Multi-layer transcript fetcher:
    Layer 1: DownSub Direct TimedText API (ytInitialPlayerResponse fmt=json3)
    Layer 2: youtube-transcript-api
    Layer 3: yt-dlp auto-subtitle downloader
    """
    # Layer 1: DownSub Direct TimedText Extraction
    timedtext_result = get_transcript_via_timedtext(video_id)
    if timedtext_result:
        return {
            "full_transcript": timedtext_result,
            "has_transcript": True,
            "source": "downsub-direct-timedtext"
        }

    # Layer 2: youtube-transcript-api
    try:
        api = YouTubeTranscriptApi()
        transcript_list = api.list_transcripts(video_id)
        
        transcript_obj = None
        try:
            transcript_obj = transcript_list.find_manually_created_transcript(['en', 'bn', 'hi', 'es', 'fr', 'de'])
        except Exception:
            try:
                transcript_obj = transcript_list.find_generated_transcript(['en', 'bn', 'hi', 'es', 'fr', 'de'])
            except Exception:
                for t in transcript_list:
                    transcript_obj = t
                    break

        if transcript_obj:
            fetched_data = transcript_obj.fetch()
            lines = [item.get('text', '').strip().replace('\n', ' ') for item in fetched_data if item.get('text')]
            if lines:
                return {
                    "full_transcript": " ".join(lines),
                    "has_transcript": True,
                    "source": "youtube-transcript-api"
                }
    except Exception as e:
        print(f"Layer 2 (youtube-transcript-api) failed: {e}")

    # Layer 3: yt-dlp subtitle extraction
    if url:
        yt_dlp_text = get_transcript_via_ytdlp(url, output_dir)
        if yt_dlp_text:
            return {
                "full_transcript": yt_dlp_text,
                "has_transcript": True,
                "source": "yt-dlp-subtitles"
            }

    return {
        "full_transcript": "",
        "has_transcript": False,
        "error": "No subtitles found for this video."
    }
