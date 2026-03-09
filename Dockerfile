# Build Frontend
FROM node:20-alpine as frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
# Fix Vite build memory limits if necessary
ENV NODE_OPTIONS="--max-old-space-size=4096"
RUN npm run build

# Build Backend and Final Image
FROM python:3.11-slim
WORKDIR /app

# Install system dependencies: ffmpeg for audio processing, libaubio-dev for aubio Python bindings
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libaubio-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ /app/backend/

# Copy built frontend assets
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

# Expose port (Render sets $PORT dynamically, default to 8000)
ENV PORT=8000
EXPOSE $PORT

# Run FastAPI with Uvicorn, using Render's $PORT
CMD uvicorn backend.main:app --host 0.0.0.0 --port $PORT
