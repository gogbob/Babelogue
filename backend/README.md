# Babelogue backend

FastAPI server between the browser and the GPU **audio processing service** (`../API_PCGPU.md`).
The audio service does VAD, speaker separation and speaker ID. This backend handles everything else:
sessions, chunking, utterance building, speech-to-text, translation, TTS and the transcript.

```
browser ──WS PCM16 16 kHz──▶ Chunker (5 s, 2.5 s hop) ──POST /chunks──▶ audio service (GPU)
                                                                          │ segments + speaker_id
browser ◀──WS chat events── UtteranceBuilder ◀────────────────────────────┘
                              │ open  → faster-whisper (fast)  → utterance_partial
                              │ close → faster-whisper + lang  → translate per distinct language → utterance_final
browser ──GET /tts──▶ Azure AI Speech (disk cache)
```

## Layout

```
app/
  main.py            FastAPI app; loads models once at startup (lifespan), /health
  config.py          every setting, from env vars / .env
  schemas.py         WebSocket + REST message schema (mirror: frontend/src/api/protocol.ts)
  session.py         in-memory Session (participants, transcript, clients) + per-session pipeline
  api/
    sessions.py      REST: sessions, voice check-in, transcript
    ws.py            WebSocket /ws/{session_id}
    tts.py           REST /tts
  services/
    audio_service.py client for the GPU audio service
    audio_utils.py   decode / resample / WAV encode (webm from MediaRecorder via PyAV)
    chunker.py       continuous stream -> overlapping chunks
    utterances.py    segments -> live/final utterances (overlap dedupe, unknown->known takeover)
    transcriber.py   faster-whisper (or dummy)
    translator.py    Azure AI Translator, one request per utterance for all languages (or echo)
    tts.py           Azure TTS + cache
mock_audio_service/  fake audio service with the same API, for development without the GPU box
```

## Setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt # core server
pip install -r requirements-ml.txt  # + faster-whisper (local speech-to-text)
cp .env.example .env            # then fill in Azure keys etc.
```

Translation uses **Azure AI Translator**: create a Translator (or multi-service Azure AI services) resource and put its key and region in `.env` as `AZURE_TRANSLATOR_KEY` / `AZURE_TRANSLATOR_REGION`. The F0 free tier allows 2M characters/month.

## Run

```bash
# 1. audio service: the real one on the GPU box, or the mock
uvicorn mock_audio_service.main:app --port 8001
# 2. this backend: one worker only, because state lives in memory
uvicorn app.main:app --port 8000 --reload
# 3. frontend: npm run dev in ../frontend (proxies /api, /ws, /tts to :8000)
```

No GPU, no Azure? Run with `STT_BACKEND=dummy TRANSLATOR_BACKEND=echo`.

## API

| | Endpoint | |
|---|---|---|
| POST | `/api/sessions` | create a session (also creates the audio-service conversation) |
| DELETE | `/api/sessions/{id}` | end it and clear voice memory |
| POST | `/api/sessions/{id}/participants` | voice check-in, multipart `name`, `language`, `audio_file` (~5 s, WAV or webm) → participant with color `slot` 1–4 |
| DELETE | `/api/sessions/{id}/participants/{pid}` | remove a participant |
| GET | `/api/sessions/{id}/transcript` | finalized messages |
| GET | `/tts?text=…&language=fr` | MP3, usable directly as `<audio src>` |
| WS | `/ws/{id}` | binary PCM16 mono 16 kHz up, JSON events both ways (see `app/schemas.py`) |
| GET | `/health` | backend + audio service status |

## Latency notes

A speaker's bubble closes when the newest chunk shows ≥ 0.7 s of silence after them, so with 5 s chunks
every 2.5 s, a finished sentence is detected roughly 2.5–5 s after it ends, plus Whisper and translation time.
To get under the 5 s target, lower `CHUNK_SECONDS`/`HOP_SECONDS` (e.g. 3 / 1.5; speaker ID needs ≥ 1 s
segments) and send `{"type":"flush"}` when the mic is released.
