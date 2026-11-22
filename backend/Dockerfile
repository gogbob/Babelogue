# Babelogue FastAPI API and optional mock GPU service. Core dependencies only.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# libsndfile1 supports WAV/FLAC via soundfile; libgomp1 for numerical libraries.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libsndfile1 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt
RUN python -m pip install -r requirements.txt

COPY app/ ./app/
COPY mock_audio_service/ ./mock_audio_service/

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/tts_cache \
    && chown -R appuser:appuser /app/tts_cache
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
