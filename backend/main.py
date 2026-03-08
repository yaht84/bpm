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

app = FastAPI(title="BPM Modifier API")

# Define path to the built frontend
FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")

# Enable CORS for the React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins for local dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Original-Tempo", "X-Stretch-Factor"],
)

TEMP_DIR = tempfile.gettempdir()

def detect_bpm(input_path: str):
    y, sr = librosa.load(input_path, sr=None)
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    tempo = np.atleast_1d(tempo)[0]
    if tempo == 0:
        raise ValueError("Could not detect tempo of the audio file.")
    return float(tempo)

def process_audio(input_path: str, output_path: str, target_bpm: float, quantize: bool, input_bpm: float = None):
    """
    If quantize is True, we assume the user wants to quantize a drum loop 
    (detect current tempo and stretch to target tempo).
    If quantize is False, we just change the tempo assuming the current tempo is irrelevant
    or we just blindly stretch by a factor.
    For simplicity and based on previous iteration, we detect tempo and stretch.
    """
    try:
        y, sr = librosa.load(input_path, sr=None)
        
        # Use target tempo or detect
        if input_bpm is not None and input_bpm > 0:
            tempo = input_bpm
        else:
            tempo = detect_bpm(input_path)

        # If we just want a simple stretch, we still need a reference. 
        # Here we just stretch from detected tempo to target.
        # Librosa rate: rate > 1 speeds up, rate < 1 slows down.
        # We need rate = target / current
        stretch_factor = target_bpm / tempo

        # Apply time stretch
        y_stretched = librosa.effects.time_stretch(y, rate=stretch_factor)
        
        # Save output
        sf.write(output_path, y_stretched, sr)
        return {"original_tempo": float(tempo), "target_tempo": target_bpm, "stretch_factor": stretch_factor}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/process-audio")
async def process_audio_endpoint(
    file: UploadFile = File(...),
    targetBpm: float = Form(88.0),
    quantize: bool = Form(True),
    inputBpm: float = Form(None)
):
    if not file.filename.lower().endswith(('.mp3', '.wav', '.flac', '.ogg', '.m4a')):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload an audio file.")

    # Unique filenames to avoid clashes
    job_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1]
    input_path = os.path.join(TEMP_DIR, f"input_{job_id}{ext}")
    output_path = os.path.join(TEMP_DIR, f"output_{job_id}.wav")

    # Save uploaded file
    try:
        with open(input_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

    # Process audio
    metadata = process_audio(input_path, output_path, targetBpm, quantize, inputBpm)

    # Return JSON with job_id
    if not os.path.exists(output_path):
        raise HTTPException(status_code=500, detail="Processing failed, output file not found.")

    return {
        "job_id": job_id,
        "original_tempo": metadata["original_tempo"],
        "target_tempo": targetBpm,
        "stretch_factor": metadata["stretch_factor"]
    }

@app.get("/api/download/{job_id}/{filename}")
async def download_audio(job_id: str, filename: str):
    output_path = os.path.join(TEMP_DIR, f"output_{job_id}.wav")
    if not os.path.exists(output_path):
        raise HTTPException(status_code=404, detail="File not found.")
        
    # FastAPI's FileResponse automatically sets the Content-Disposition header safely 
    # when filename is provided, which is fully compatible with Safari across origins.
    return FileResponse(
        path=output_path, 
        media_type="audio/wav", 
        filename=filename
    )

@app.post("/api/analyze")
async def analyze_audio(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(('.mp3', '.wav', '.flac', '.ogg', '.m4a')):
        raise HTTPException(status_code=400, detail="Invalid file type.")
    
    job_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1]
    input_path = os.path.join(TEMP_DIR, f"analyze_{job_id}{ext}")
    
    try:
        with open(input_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        tempo = detect_bpm(input_path)
        os.remove(input_path)
        return {"bpm": tempo}
    except Exception as e:
        if os.path.exists(input_path):
            os.remove(input_path)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def read_root():
    return {"message": "BPM Modifier API is running. Use /process-audio to process files."}

# --- Static File Serving for Production (e.g. Render) ---
# Check if the built frontend directory exists (it will in the Docker container)
if os.path.isdir(FRONTEND_DIST):
    # Mount the 'assets' directory explicitly so Vite's /assets/... URLs work 
    # Must be mounted *before* the catch-all
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")
    
    # Explicitly serve index.html at exactly the root URL
    @app.get("/")
    async def serve_root():
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))
        
    # Catch-all route to serve the SPA index.html for any unmatched route
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        # Serve specific files if requested directly (like favicon, logo)
        file_path = os.path.join(FRONTEND_DIST, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
            
        # Fallback to index.html for client-side routing
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))
