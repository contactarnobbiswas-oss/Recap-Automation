import os
import re
from google import genai
from google.genai import types
from typing import List

def get_gemini_client(api_key: str = None) -> genai.Client:
    key = api_key or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise ValueError("Gemini API Key is missing. Please set GEMINI_API_KEY environment variable or pass api_key.")
    return genai.Client(api_key=key)


def clean_title_punctuation_and_case(title: str) -> str:
    """
    Removes all commas, colons, semicolons, dashes, quotes, and special symbols from title.
    Applies clean YouTube Title Case (capitalizing major words).
    """
    # Remove punctuation symbols
    cleaned = re.sub(r'[:,;\-"\'\(\)\[\]\{\}\?!|\*#]', ' ', title)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    # Apply Title Case (Capitalize major words)
    words = cleaned.split()
    minor_words = {'a', 'an', 'the', 'and', 'but', 'or', 'for', 'nor', 'on', 'at', 'to', 'from', 'by', 'with', 'in', 'of'}
    title_cased = []
    
    for idx, word in enumerate(words):
        lower_w = word.lower()
        if idx == 0 or idx == len(words) - 1 or lower_w not in minor_words:
            title_cased.append(word.capitalize())
        else:
            title_cased.append(lower_w)
            
    return " ".join(title_cased)


def strip_transcript_noise_and_music(text: str) -> str:
    if not text:
        return ""
    
    cleaned = re.sub(r'\[\s*(music|applause|laughter|chuckles|cheering|sound|audio|unclear|sighs|singing|gasp|screaming|background music)\s*\]', '', text, flags=re.IGNORECASE)
    cleaned = re.sub(r'\(\s*(music|applause|laughter|chuckles|cheering|sound|audio|unclear|sighs|singing|gasp|screaming|background music)\s*\)', '', text, flags=re.IGNORECASE)
    cleaned = re.sub(r'\[[^\]]*music[^\]]*\]', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\([^\)]*music[^\)]*\)', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


def rewrite_titles(original_title: str, api_key: str = None) -> str:
    """
    Step 2: Rewrites original YouTube title into 1 ultra-high CTR viral YouTube title.
    Rules:
    - Retains 100% of the intense viral hook words ("Cult Family", "Kidnapped", "Forced to Become", "Missing Sister").
    - Equal to or MORE engaging and viral than the original title.
    - Title Case formatting.
    - Zero commas, zero colons, zero dashes, zero punctuation.
    """
    client = get_gemini_client(api_key)
    prompt = f"""
You are an elite viral YouTube movie recap title strategist and copywriter.
Analyze this high-CTR video title: "{original_title}"

Rewrite it into EXACTLY ONE single, insanely powerful, high-CTR viral YouTube title.

STRICT VIRAL RULES:
1. Retain 100% of the intense emotional triggers, curiosity hooks, and core plot elements (such as "Cult Family", "Kidnapped / Captured", "Forced to Act / Become", "Missing Sister / Lost Sister").
2. Match or EXCEED the viral intensity and click-through rate (CTR) of the original title.
3. Completely rephrase sentence phrasing so it is 100% original, copyright-free, and avoids YouTube duplicate metadata flags.
4. Format in proper YouTube Title Case (e.g. "Cult Family Kidnaps Girl and Forces Her to Become Their Missing Sister").
5. DO NOT USE ANY COMMAS (,), DO NOT USE ANY COLONS (:), DO NOT USE SEMICOLONS (;), DO NOT USE DASHES (-), DO NOT USE QUOTES (").
6. Output ONLY the single rewritten title text without any quotes, markdown, or intro commentary.
"""

    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.3,
        )
    )

    raw_output = response.text.strip().replace('\n', ' ')
    raw_output = re.sub(r'^[1-9][.\-\)]\s*', '', raw_output).strip(' "\'')
    
    final_title = clean_title_punctuation_and_case(raw_output)
    return final_title if final_title else clean_title_punctuation_and_case(original_title)


def split_script_into_chunks(text: str, chunk_size: int = 4000) -> List[str]:
    # Flatten text to continuous string first
    clean_text = strip_transcript_noise_and_music(text)
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()

    if len(clean_text) <= chunk_size:
        return [clean_text]

    chunks = []
    start = 0
    while start < len(clean_text):
        end = start + chunk_size
        if end >= len(clean_text):
            chunks.append(clean_text[start:].strip())
            break
        
        # Find sentence boundary near chunk_size
        sentence_end = clean_text.rfind('. ', start, end)
        if sentence_end != -1 and sentence_end > start + 1000:
            chunks.append(clean_text[start:sentence_end + 1].strip())
            start = sentence_end + 2
        else:
            chunks.append(clean_text[start:end].strip())
            start = end

    return chunks


def rewrite_transcript_line_by_line(transcript: str, api_key: str = None) -> str:
    """
    Step 3: Rewrites large movie recap scripts in AI chunks.
    Strips all noise, music, and newlines. Outputs clean paragraph blocks per chunk.
    """
    if not transcript or not transcript.strip():
        return ""

    cleaned_transcript = strip_transcript_noise_and_music(transcript)
    cleaned_transcript = re.sub(r'\s+', ' ', cleaned_transcript).strip()

    client = get_gemini_client(api_key)
    chunks = split_script_into_chunks(cleaned_transcript, chunk_size=4000)
    rewritten_chunks = []

    print(f"[AI Rewriter] Processing full transcript script ({len(cleaned_transcript)} chars) in {len(chunks)} AI chunks...")

    for idx, chunk in enumerate(chunks):
        print(f"[AI Rewriter] Rewriting script chunk {idx + 1}/{len(chunks)}...")
        prompt = f"""
You are a top-tier professional video scriptwriter and movie recap narrator.
Your task is to REWRITE section {idx + 1} of this movie recap script into 100% CLEAN, VOICE-OVER READY narration text.

STRICT NARRATION RULES:
1. Maintain 100% exact story progression, character names, narrative arc, and line-by-line sequence of events.
2. DO NOT SUMMARIZE, CONDENSE, OR SHORTEN THE STORY. Rewrite every detail completely.
3. REMOVE ALL stage directions, non-verbal sound cues, bracketed noise indicators (like [Music], (Laughter), [Applause]), speaker labels, or markdown marks.
4. Completely rephrase sentence structures, vocabulary, and expressions to make it 100% original, fluid, engaging, and plagiarism-free.
5. Output ONLY the final rewritten voiceover-ready narration text as a single continuous paragraph without internal line breaks or introductory meta-text.

Original Script Section:
{chunk}
"""

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
            )
        )

        chunk_text = response.text.strip()
        chunk_text = strip_transcript_noise_and_music(chunk_text)
        chunk_text = re.sub(r'\s+', ' ', chunk_text).strip()
        if chunk_text:
            rewritten_chunks.append(chunk_text)

    # Return distinct paragraph blocks for each chunk
    final_script = "\n\n".join(rewritten_chunks)
    return final_script
