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

# Install system dependencies required for librosa and soundfile
RUN apt-get update && apt-get install -y \
    libsndfile1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ /app/backend/

# Copy built frontend assets
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

# Expose port
EXPOSE 8000

# Run FastAPI with Uvicorn, serving the frontend via static mounts
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
