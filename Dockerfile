FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg curl libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN mkdir -p /app/models && for m in full heavy; do curl -fsSL -o /app/models/pose_landmarker_$m.task \
    https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_$m/float16/latest/pose_landmarker_$m.task; done

COPY app ./app
ENV DATA_DIR=/data POSE_MODEL=/app/models/pose_landmarker_heavy.task PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-keep-alive", "120"]
