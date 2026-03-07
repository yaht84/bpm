from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import librosa
import numpy as np
import soundfile as sf
import os
import tempfile
import uuid

app = FastAPI(title="BPM Modifier API")

# Enable CORS for the React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins for local dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TEMP_DIR = tempfile.gettempdir()

def process_audio(input_path: str, output_path: str, target_bpm: float, quantize: bool):
    """
    If quantize is True, we assume the user wants to quantize a drum loop 
    (detect current tempo and stretch to target tempo).
    If quantize is False, we just change the tempo assuming the current tempo is irrelevant
    or we just blindly stretch by a factor.
    For simplicity and based on previous iteration, we detect tempo and stretch.
    """
    try:
        y, sr = librosa.load(input_path, sr=None)
        
        # Detect current tempo
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        tempo = np.atleast_1d(tempo)[0]
        
        if tempo == 0:
            raise ValueError("Could not detect tempo of the audio file.")

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


@app.post("/process-audio")
async def process_audio_endpoint(
    file: UploadFile = File(...),
    targetBpm: float = Form(88.0),
    quantize: bool = Form(True)
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
    metadata = process_audio(input_path, output_path, targetBpm, quantize)

    # Return the processed file
    if not os.path.exists(output_path):
        raise HTTPException(status_code=500, detail="Processing failed, output file not found.")

    return FileResponse(
        path=output_path, 
        media_type="audio/wav", 
        filename=f"processed_{targetBpm}bpm.wav",
        headers={
            "X-Original-Tempo": str(round(metadata["original_tempo"], 2)),
            "X-Stretch-Factor": str(round(metadata["stretch_factor"], 4))
        }
    )

@app.get("/")
def read_root():
    return {"message": "BPM Modifier API is running. Use /process-audio to process files."}
