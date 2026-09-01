FROM python:3.10-slim

WORKDIR /app

# Install ffmpeg for Edge TTS & audio processing
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend and frontend source code
COPY backend/ ./backend/
COPY web/ ./web/

# Set Python module search path
ENV PYTHONPATH=/app/backend

# Expose port
EXPOSE 8000

# Run FastAPI app using python module syntax
CMD ["python", "backend/main.py"]
