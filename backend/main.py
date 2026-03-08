from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import librosa
import numpy as np
import soundfile as sf
import os
import tempfile
import uuid
import subprocess
import logging
import shutil

# Configure logging so we can see errors in Render logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="BPM Modifier API")

# Define path to the built frontend
FRONTEND_DIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend", "dist")

# Enable CORS for the React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Original-Tempo", "X-Stretch-Factor"],
)

TEMP_DIR = tempfile.gettempdir()


def convert_to_wav(input_path: str, output_path: str, duration: float = None, sr: int = None, mono: bool = False):
    """Use ffmpeg to convert audio to WAV. This is MUCH faster and uses far less memory than librosa.load on MP3s."""
    cmd = ["ffmpeg", "-y", "-i", input_path]
    if duration:
        cmd.extend(["-t", str(duration)])
    if sr:
        cmd.extend(["-ar", str(sr)])
    if mono:
        cmd.extend(["-ac", "1"])
    cmd.append(output_path)
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        logger.error(f"ffmpeg failed: {result.stderr.decode()}")
        raise ValueError(f"ffmpeg conversion failed: {result.stderr.decode()[:200]}")


def detect_bpm(input_path: str):
    """Detect BPM using only the first 30 seconds at low sample rate to stay within 512MB RAM."""
    cut_path = input_path + "_detect.wav"
    try:
        # Extract first 30s, mono, 22050Hz — this creates a ~2.5MB file max
        convert_to_wav(input_path, cut_path, duration=30.0, sr=22050, mono=True)
        y, sr = librosa.load(cut_path, sr=None)
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        tempo = np.atleast_1d(tempo)[0]
        if tempo == 0:
            raise ValueError("Could not detect tempo of the audio file.")
        return float(tempo)
    finally:
        if os.path.exists(cut_path):
            os.remove(cut_path)


def process_audio(input_path: str, output_path: str, target_bpm: float, quantize: bool, input_bpm: float = None):
    """
    Detect current BPM (or use provided), then time-stretch to target BPM.
    Uses ffmpeg pre-conversion + downsampled librosa to stay within memory limits.
    """
    # Convert to mono 22050Hz WAV to keep memory low even for full-length tracks
    wav_path = input_path + "_full.wav"
    try:
        convert_to_wav(input_path, wav_path, sr=22050, mono=True)
        y, sr = librosa.load(wav_path, sr=None)

        # Use provided BPM or detect
        if input_bpm is not None and input_bpm > 0:
            tempo = input_bpm
        else:
            tempo = detect_bpm(input_path)

        stretch_factor = target_bpm / tempo

        # Apply time stretch
        y_stretched = librosa.effects.time_stretch(y, rate=stretch_factor)

        # Save output
        sf.write(output_path, y_stretched, sr)
        return {"original_tempo": float(tempo), "target_tempo": target_bpm, "stretch_factor": stretch_factor}
    except Exception as e:
        logger.error(f"process_audio failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(wav_path):
            os.remove(wav_path)


# ==================== API ENDPOINTS ====================

@app.post("/api/analyze")
def analyze_audio(file: UploadFile = File(...)):
    logger.info(f"Analyze request received: {file.filename}")
    if not file.filename.lower().endswith(('.mp3', '.wav', '.flac', '.ogg', '.m4a')):
        raise HTTPException(status_code=400, detail="Invalid file type.")

    job_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1]
    input_path = os.path.join(TEMP_DIR, f"analyze_{job_id}{ext}")

    try:
        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        logger.info(f"File saved to {input_path}. Starting BPM detection...")

        tempo = detect_bpm(input_path)
        logger.info(f"BPM detected: {tempo}")
        return {"bpm": tempo}
    except Exception as e:
        logger.error(f"Analyze failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(input_path):
            os.remove(input_path)


@app.post("/api/process-audio")
def process_audio_endpoint(
    file: UploadFile = File(...),
    targetBpm: float = Form(88.0),
    quantize: bool = Form(True),
    inputBpm: float = Form(None)
):
    if not file.filename.lower().endswith(('.mp3', '.wav', '.flac', '.ogg', '.m4a')):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload an audio file.")

    job_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1]
    input_path = os.path.join(TEMP_DIR, f"input_{job_id}{ext}")
    output_path = os.path.join(TEMP_DIR, f"output_{job_id}.wav")

    try:
        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

    metadata = process_audio(input_path, output_path, targetBpm, quantize, inputBpm)

    if not os.path.exists(output_path):
        raise HTTPException(status_code=500, detail="Processing failed, output file not found.")

    return {
        "job_id": job_id,
        "original_tempo": metadata["original_tempo"],
        "target_tempo": targetBpm,
        "stretch_factor": metadata["stretch_factor"]
    }


@app.get("/api/download/{job_id}/{filename}")
def download_audio(job_id: str, filename: str):
    output_path = os.path.join(TEMP_DIR, f"output_{job_id}.wav")
    if not os.path.exists(output_path):
        raise HTTPException(status_code=404, detail="File not found.")
    return FileResponse(path=output_path, media_type="audio/wav", filename=filename)


# ==================== HEALTH CHECK ====================

@app.get("/api/health")
async def health_check():
    return {"status": "ok"}


# ==================== STATIC FILE SERVING (Production only) ====================
# In Docker, the built Vite frontend is at /app/frontend/dist
# This block MUST come LAST so API routes take priority

if os.path.isdir(FRONTEND_DIST):
    logger.info(f"Frontend dist found at {FRONTEND_DIST}, mounting static files")

    # Mount assets subdirectory for Vite's hashed JS/CSS bundles
    assets_dir = os.path.join(FRONTEND_DIST, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/")
    async def serve_root():
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        file_path = os.path.join(FRONTEND_DIST, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))
else:
    logger.info(f"No frontend dist at {FRONTEND_DIST}, running in API-only mode")

    @app.get("/")
    async def api_root():
        return {"message": "BPM Modifier API is running."}
