import os
import time
import uuid
import random
import shutil
import textwrap
import subprocess
import requests
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="Meme Video Renderer API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

VIDEOS_DIR = Path("/app/videos")
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

LOCAL_AUDIO = Path(__file__).parent / "gymnopedie.ogg"

# Musique douce libre de droits par défaut (Erik Satie - Gymnopédie No. 1, piano doux et contemplatif)
DEFAULT_AUDIO_TRACKS = [
    "https://upload.wikimedia.org/wikipedia/commons/b/b7/Gymnopedie_No._1..ogg"
]

LOCAL_FONT = Path(__file__).parent / "Montserrat-Bold.ttf"

FONT_CANDIDATES = [
    str(LOCAL_FONT),
    "/app/Montserrat-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]

def get_font_path():
    for f in FONT_CANDIDATES:
        if os.path.exists(f):
            return f
    return None

class RenderRequest(BaseModel):
    video_url: str
    text: str
    audio_url: Optional[str] = None
    duration: Optional[int] = 7
    font_size: Optional[int] = 60

def cleanup_old_videos(max_age_seconds: int = 10800):
    now = time.time()
    for file in VIDEOS_DIR.glob("*.mp4"):
        try:
            if now - file.stat().st_mtime > max_age_seconds:
                file.unlink(missing_ok=True)
        except Exception:
            pass

@app.get("/")
@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "Meme Video Renderer API",
        "message": "Ready to render Reels and TikToks with TikTok-style Montserrat typography"
    }

@app.post("/render")
async def render_video(req: RenderRequest, request: Request, background_tasks: BackgroundTasks):
    background_tasks.add_task(cleanup_old_videos)

    task_id = str(uuid.uuid4())[:8]
    temp_dir = Path(f"/tmp/render_{task_id}")
    temp_dir.mkdir(parents=True, exist_ok=True)

    input_video_path = temp_dir / "input.mp4"
    input_audio_path = temp_dir / "audio.track"
    text_file_path = temp_dir / "text.txt"
    output_filename = f"meme_{task_id}_{int(time.time())}.mp4"
    output_video_path = VIDEOS_DIR / output_filename

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        # 1. Télécharger la vidéo source
        resp = requests.get(req.video_url, headers=headers, stream=True, timeout=30)
        if resp.status_code != 200:
            raise HTTPException(
                status_code=400,
                detail=f"Impossible de télécharger la vidéo source (code HTTP {resp.status_code})"
            )
        with open(input_video_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)

        # 2. Gestion de la musique douce (Fichier local en priorité, sinon téléchargement)
        has_audio = False
        audio_error_detail = None

        if LOCAL_AUDIO.exists() and not req.audio_url:
            input_audio_path = LOCAL_AUDIO
            has_audio = True
        else:
            target_audio_url = req.audio_url if req.audio_url else random.choice(DEFAULT_AUDIO_TRACKS)
            input_audio_path = temp_dir / "audio.ogg"
            try:
                audio_resp = requests.get(target_audio_url, headers=headers, stream=True, timeout=30)
                if audio_resp.status_code == 200:
                    with open(input_audio_path, "wb") as f:
                        for chunk in audio_resp.iter_content(chunk_size=512 * 1024):
                            if chunk:
                                f.write(chunk)
                    has_audio = True
                else:
                    audio_error_detail = f"HTTP {audio_resp.status_code}"
            except Exception as e:
                audio_error_detail = str(e)
                has_audio = False

        # 3. Formater le texte : chaque ligne est centrée individuellement (style citation / meme TikTok)
        clean_text = req.text.strip().strip('"').strip("'")
        lines = textwrap.wrap(clean_text, width=24)
        if not lines:
            lines = [clean_text]

        font_path = get_font_path()
        font_param = f":fontfile='{font_path}'" if font_path else ""

        font_size = req.font_size or 58
        line_spacing = 24
        line_height = font_size + line_spacing
        total_text_height = (len(lines) - 1) * line_height + font_size

        drawtext_filters = []
        for idx, line in enumerate(lines):
            line_file = temp_dir / f"line_{idx}.txt"
            with open(line_file, "w", encoding="utf-8") as f:
                f.write(line)
            escaped_line_path = str(line_file).replace(":", "\\:")
            y_pos = f"(h-{total_text_height})/2+{idx * line_height}"
            drawtext_filters.append(
                f"drawtext=textfile='{escaped_line_path}'{font_param}:"
                f"fontsize={font_size}:fontcolor=white:"
                f"x=(w-text_w)/2:y={y_pos}:"
                f"borderw=5:bordercolor=black:"
                f"shadowcolor=black@0.8:shadowx=3:shadowy=3"
            )

        vf_filter = (
            "scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920," +
            ",".join(drawtext_filters)
        )

        fade_out_start = max(1.0, req.duration - 1.0)

        if has_audio:
            filter_complex = (
                f"[0:v]{vf_filter}[v];"
                f"[1:a]volume=0.85,afade=t=in:st=0:d=0.5,afade=t=out:st={fade_out_start}:d=1.0[a]"
            )
            cmd = [
                "ffmpeg",
                "-y",
                "-threads", "1",
                "-i", str(input_video_path),
                "-i", str(input_audio_path),
                "-filter_complex", filter_complex,
                "-map", "[v]",
                "-map", "[a]",
                "-t", str(req.duration),
                "-r", "30",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-tune", "fastdecode",
                "-crf", "24",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "128k",
                "-shortest",
                "-movflags", "+faststart",
                str(output_video_path)
            ]
        else:
            cmd = [
                "ffmpeg",
                "-y",
                "-threads", "1",
                "-i", str(input_video_path),
                "-vf", vf_filter,
                "-t", str(req.duration),
                "-r", "30",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-tune", "fastdecode",
                "-crf", "24",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "96k",
                "-movflags", "+faststart",
                str(output_video_path)
            ]

        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"Erreur d'encodage FFmpeg: {result.stderr[-500:]}"
            )

        forwarded_host = request.headers.get("x-forwarded-host")
        forwarded_proto = request.headers.get("x-forwarded-proto", "https")
        if forwarded_host:
            base_url = f"{forwarded_proto}://{forwarded_host}/"
        else:
            base_url = str(request.base_url)

        final_video_url = f"{base_url.rstrip('/')}/videos/{output_filename}"

        return {
            "success": True,
            "video_url": final_video_url,
            "filename": output_filename,
            "duration": req.duration,
            "has_audio": has_audio,
            "audio_error": audio_error_detail,
            "phrase": clean_text
        }

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

@app.get("/videos/{filename}")
async def get_video(filename: str):
    file_path = VIDEOS_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Vidéo introuvable ou expirée.")
    return FileResponse(
        path=str(file_path),
        media_type="video/mp4",
        filename=filename
    )
