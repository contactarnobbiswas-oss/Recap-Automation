import os
import time
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from db import (
    init_db, authenticate_user, create_session, get_session_user,
    update_user_api_key, get_user_today_usage_count, log_activity,
    get_all_users_with_stats, get_recent_activity_logs, create_user, update_user_limit
)
from services.youtube import extract_video_id, get_video_metadata, get_transcript
from services.ai_rewriter import rewrite_titles, rewrite_transcript_line_by_line
from services.image_processor import process_thumbnail
from services.tts_engine import get_available_voices, generate_voiceover

app = FastAPI(title="Recap Automation API with Multi-User Auth", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)
WEB_DIR = os.path.join(PROJECT_DIR, "web")
DOWNLOADS_DIR = os.path.join(BASE_DIR, "downloads")

os.makedirs(DOWNLOADS_DIR, exist_ok=True)
init_db()

app.mount("/downloads", StaticFiles(directory=DOWNLOADS_DIR), name="downloads")

if os.path.exists(WEB_DIR):
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

@app.get("/")
def serve_dashboard():
    index_path = os.path.join(WEB_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Recap Automation API active"}

# Auth Dependency
def get_current_user(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    if not authorization:
        raise HTTPException(status_code=401, detail="Authentication required. Please log in.")
    
    token = authorization.replace("Bearer ", "").strip()
    user = get_session_user(token)
    if not user:
        raise HTTPException(status_code=401, detail="Session expired. Please log in again.")
    return user

# Pydantic Models
class LoginRequest(BaseModel):
    username: str
    password: str

class UpdateKeyRequest(BaseModel):
    gemini_api_key: str

class CreateUserRequest(BaseModel):
    username: str
    password: str
    daily_limit: int = 5

class UpdateLimitRequest(BaseModel):
    user_id: int
    daily_limit: int

class ExtractRequest(BaseModel):
    url: str

class RewriteRequest(BaseModel):
    title: str
    transcript: str
    thumbnail_url: str
    gemini_api_key: Optional[str] = None
    flip_thumbnail: bool = True

class TTSGenerateRequest(BaseModel):
    text: str
    voice: str = "en-US-AvaMultilingualNeural"
    rate: str = "+0%"
    pitch: str = "+0Hz"


@app.get("/api/health")
def health_check():
    return {"status": "ok", "app": "Recap Automation Multi-User Engine", "message": "Operational"}


# AUTH & USER ROUTES
@app.post("/api/login")
def login(req: LoginRequest):
    user = authenticate_user(req.username, req.password)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid username or password.")
    
    token = create_session(user)
    used_today = get_user_today_usage_count(user["id"])
    
    return {
        "success": True,
        "token": token,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "role": user["role"],
            "daily_limit": user["daily_limit"],
            "used_today": used_today,
            "has_api_key": bool(user.get("gemini_api_key"))
        }
    }


@app.get("/api/me")
def get_me(user: Dict[str, Any] = Depends(get_current_user)):
    used_today = get_user_today_usage_count(user["id"])
    key = user.get("gemini_api_key", "")
    masked_key = (key[:4] + "••••••••" + key[-4:]) if len(key) >= 8 else ("••••" if key else "")
    
    return {
        "success": True,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "role": user["role"],
            "daily_limit": user["daily_limit"],
            "used_today": used_today,
            "has_api_key": bool(key),
            "masked_api_key": masked_key
        }
    }


@app.post("/api/user/key")
def save_user_api_key(req: UpdateKeyRequest, user: Dict[str, Any] = Depends(get_current_user)):
    update_user_api_key(user["id"], req.gemini_api_key)
    return {"success": True, "message": "Gemini API Key saved securely."}


# ADMIN ROUTES
@app.get("/api/admin/users")
def list_admin_users(user: Dict[str, Any] = Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required.")
    
    users = get_all_users_with_stats()
    return {"success": True, "users": users}


@app.post("/api/admin/users")
def admin_create_editor(req: CreateUserRequest, user: Dict[str, Any] = Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required.")
    
    try:
        new_user = create_user(req.username, req.password, role="editor", daily_limit=req.daily_limit)
        return {"success": True, "user": new_user}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/admin/users/limit")
def admin_update_limit(req: UpdateLimitRequest, user: Dict[str, Any] = Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required.")
    
    update_user_limit(req.user_id, req.daily_limit)
    return {"success": True, "message": "Daily limit updated."}


@app.get("/api/admin/logs")
def list_admin_logs(user: Dict[str, Any] = Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required.")
    
    logs = get_recent_activity_logs(100)
    return {"success": True, "logs": logs}


# CONTENT GENERATION ROUTES WITH QUOTA ENFORCEMENT
@app.post("/api/extract")
def extract_youtube_info(req: ExtractRequest, user: Dict[str, Any] = Depends(get_current_user)):
    try:
        url = req.url.strip()
        video_id = extract_video_id(url)
        
        metadata = get_video_metadata(url, DOWNLOADS_DIR)
        transcript_data = get_transcript(video_id, url=url, output_dir=DOWNLOADS_DIR)
        
        log_activity(user["id"], user["username"], "extract_media", metadata["title"])

        return {
            "success": True,
            "video_id": video_id,
            "title": metadata["title"],
            "channel": metadata["channel"],
            "duration": metadata["duration"],
            "thumbnail_url": metadata["thumbnail_url"],
            "video_url": f"/downloads/{metadata['video_filename']}",
            "transcript": transcript_data["full_transcript"],
            "has_transcript": transcript_data["has_transcript"]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/rewrite")
def rewrite_content(req: RewriteRequest, user: Dict[str, Any] = Depends(get_current_user)):
    # Check Daily Quota for Editors
    used_today = get_user_today_usage_count(user["id"])
    if user["role"] != "admin" and used_today >= user["daily_limit"]:
        raise HTTPException(
            status_code=429,
            detail=f"Daily quota reached! You have used {used_today}/{user['daily_limit']} generations today. Try again tomorrow or contact admin."
        )

    # Use saved user API key if not passed
    api_key = req.gemini_api_key or user.get("gemini_api_key")
    if not api_key:
        raise HTTPException(status_code=400, detail="Gemini API Key is missing. Please save your API key in Settings.")

    try:
        single_title = rewrite_titles(req.title, api_key)
        
        rewritten_transcript = ""
        if req.transcript:
            rewritten_transcript = rewrite_transcript_line_by_line(req.transcript, api_key)
            
        processed_thumb_filename = f"thumb_flip_{int(time.time())}.jpg"
        processed_thumb_path = os.path.join(DOWNLOADS_DIR, processed_thumb_filename)
        process_thumbnail(req.thumbnail_url, processed_thumb_path, flip_horizontal=req.flip_thumbnail)
        
        # Log generation & increment quota
        log_activity(user["id"], user["username"], "ai_rewrite", single_title)

        return {
            "success": True,
            "rewritten_title": single_title,
            "rewritten_transcript": rewritten_transcript,
            "processed_thumbnail_url": f"/downloads/{processed_thumb_filename}",
            "used_today": used_today + 1,
            "daily_limit": user["daily_limit"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/tts/voices")
async def list_tts_voices():
    try:
        voices = await get_available_voices()
        return {"success": True, "voices": voices}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/tts/generate")
async def generate_tts_voiceover(req: TTSGenerateRequest, user: Dict[str, Any] = Depends(get_current_user)):
    try:
        if not req.text or not req.text.strip():
            raise HTTPException(status_code=400, detail="Text for voiceover cannot be empty.")
            
        timestamp = int(time.time())
        voice_short = req.voice.split("-")[-1] if "-" in req.voice else "voice"
        audio_filename = f"{voice_short}_voiceover_{timestamp}.mp3"
        output_filepath = os.path.join(DOWNLOADS_DIR, audio_filename)
        
        await generate_voiceover(
            text=req.text,
            voice=req.voice,
            output_filename=output_filepath,
            rate=req.rate,
            pitch=req.pitch
        )

        log_activity(user["id"], user["username"], "voiceover_generation", audio_filename)
        
        return {
            "success": True,
            "audio_url": f"/downloads/{audio_filename}",
            "filename": audio_filename
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
