import asyncio
import os
import time
import re
import edge_tts
from typing import Callable, Optional, List, Dict

# ১০,০০০ ক্যারেক্টারের স্মার্ট এবং সেফ স্প্লিটিং লজিক (User's exact code)
def split_text_ultra_safe(text, limit=10000):
    # কোনোভাবেই যেন শব্দ না কাটে তাই ফুলস্টপ, প্রশ্নবোধক বা বিস্ময়সূচক চিহ্ন ধরে ভাগ করা
    sentences = re.split(r'(?<=[.!?]) +', text)
    chunks = []
    current_chunk = ""
    
    for sentence in sentences:
        if len(current_chunk) + len(sentence) < limit:
            current_chunk += sentence + " "
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = sentence + " "
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    return chunks


async def get_available_voices() -> List[Dict[str, str]]:
    """
    Retrieves all available Microsoft Edge TTS Neural voices.
    """
    try:
        voices = await edge_tts.list_voices()
        formatted_voices = []
        for v in voices:
            formatted_voices.append({
                "short_name": v["ShortName"],
                "friendly_name": v.get("FriendlyName", v["ShortName"]),
                "gender": v.get("Gender", "Unknown"),
                "locale": v.get("Locale", "en-US")
            })
        formatted_voices.sort(key=lambda x: (x["locale"], x["short_name"]))
        return formatted_voices
    except Exception as e:
        print(f"Error fetching voices: {e}")
        return [
            {"short_name": "en-US-AvaMultilingualNeural", "friendly_name": "en-US - Ava (Multilingual)", "gender": "Female", "locale": "en-US"},
            {"short_name": "en-US-AndrewNeural", "friendly_name": "en-US - Andrew", "gender": "Male", "locale": "en-US"},
            {"short_name": "en-US-EmmaNeural", "friendly_name": "en-US - Emma", "gender": "Female", "locale": "en-US"},
            {"short_name": "bn-BD-NabanitaNeural", "friendly_name": "bn-BD - Nabanita", "gender": "Female", "locale": "bn-BD"}
        ]


async def generate_voiceover(
    text: str,
    voice: str,
    output_filename: str,
    rate: str = "+0%",
    pitch: str = "+0Hz",
    progress_callback: Optional[Callable[[int, int, str], None]] = None
) -> str:
    """
    User's exact Streamlit audio generation & concatenation logic.
    """
    chunks = split_text_ultra_safe(text)
    if not chunks:
        raise ValueError("No valid text provided for voiceover generation.")

    total_chunks = len(chunks)
    output_dir = os.path.dirname(output_filename)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    temp_files = []
    
    for i, chunk in enumerate(chunks):
        if chunk.strip():
            print(f"[TTS Engine] Processing chunk {i + 1}/{total_chunks} ({len(chunk)} characters)...")
            temp_file = os.path.join(output_dir if output_dir else ".", f"temp_{int(time.time())}_{i}.mp3")
            
            communicate = edge_tts.Communicate(chunk, voice, rate=rate, pitch=pitch)
            await communicate.save(temp_file)
            temp_files.append(temp_file)
            print(f"[TTS Engine] Chunk {i + 1}/{total_chunks} generated!")

    if not temp_files:
        raise RuntimeError("Failed to generate voiceover audio.")

    # সব টুকরো জোড়া লাগানো (User's exact file merge logic)
    print(f"[TTS Engine] Merging {len(temp_files)} chunks into final output '{output_filename}'...")
    with open(output_filename, 'wb') as outfile:
        for tf in temp_files:
            if os.path.exists(tf):
                with open(tf, 'rb') as infile:
                    outfile.write(infile.read())
                try:
                    os.remove(tf)
                except Exception:
                    pass

    print(f"[TTS Engine] Voiceover generation complete!")
    return output_filename
