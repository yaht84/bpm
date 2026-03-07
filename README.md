# TempoSculpt

A professional, modern web application for audio quantization and tempo alteration.

## Architecture

This application consists of two parts:
1. **Frontend**: React + Vite + Vanilla CSS
2. **Backend**: FastAPI (Python) using `librosa` for audio processing

## How to Run Locally

### 1. Start the Backend

Open a terminal in the project root:

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

*Note: The API will run on http://localhost:8000*

### 2. Start the Frontend

Open a second terminal in the project root:

```bash
cd frontend
npm install
npm run dev
```

*Note: The frontend will typically run on http://localhost:5173*
