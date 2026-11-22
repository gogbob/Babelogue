"""Stand-in for the GPU audio processing service (same API as API_PCGPU.md), for development
without the GPU box. No separation and a crude spectral "voiceprint": good enough to exercise
the pipeline, not to tell real voices apart reliably.

Run from backend/:  uvicorn mock_audio_service.main:app --port 8001
"""

import base64
import io
import uuid

import numpy as np
import soundfile as sf
from fastapi import FastAPI, Form, HTTPException, UploadFile

RATE = 16_000
FRAME = 480  # 30 ms
THRESHOLD = 0.4  # same as the real service

app = FastAPI(title="Mock audio service")
conversations: dict[str, dict[str, np.ndarray]] = {}  # conversation -> speaker -> embedding


def load(data: bytes) -> np.ndarray:
    audio, rate = sf.read(io.BytesIO(data), dtype="float32", always_2d=True)
    audio = audio.mean(axis=1)
    if rate != RATE:
        audio = np.interp(np.linspace(0, len(audio), int(len(audio) * RATE / rate), endpoint=False),
                          np.arange(len(audio)), audio).astype(np.float32)
    return audio


def speech_mask(audio: np.ndarray) -> np.ndarray:
    """Energy VAD per 30 ms frame."""
    n = len(audio) // FRAME
    if n == 0:
        return np.zeros(0, bool)
    rms = np.sqrt((audio[: n * FRAME].reshape(n, FRAME) ** 2).mean(axis=1))
    return rms > max(0.01, 0.1 * rms.max())


def regions(mask: np.ndarray, min_gap: int = 10, min_len: int = 8) -> list[tuple[int, int]]:
    """Frame-index speech regions, merging gaps shorter than min_gap frames (300 ms)."""
    out: list[list[int]] = []
    for i, on in enumerate(mask):
        if not on:
            continue
        if out and i - out[-1][1] <= min_gap:
            out[-1][1] = i + 1
        else:
            out.append([i, i + 1])
    return [(a, b) for a, b in out if b - a >= min_len]


def embed(audio: np.ndarray) -> np.ndarray:
    """Mean log energy in 40 bands. A toy stand-in for ECAPA-TDNN."""
    spec = np.abs(np.fft.rfft(audio[: len(audio) // 512 * 512].reshape(-1, 512) * np.hanning(512), axis=1))
    bands = np.array_split(spec[:, 4:200], 40, axis=1)
    e = np.log(np.stack([b.mean(axis=1) for b in bands], axis=1) + 1e-6).mean(axis=0)
    e -= e.mean()
    return e / (np.linalg.norm(e) + 1e-9)


def wav_b64(audio: np.ndarray) -> str:
    buf = io.BytesIO()
    sf.write(buf, audio, RATE, format="WAV", subtype="PCM_16")
    return base64.b64encode(buf.getvalue()).decode()


def memory(conversation_id: str) -> dict[str, np.ndarray]:
    if conversation_id not in conversations:
        raise HTTPException(404, "conversation not found")
    return conversations[conversation_id]


@app.get("/health")
def health():
    return {"status": "ready", "models_loaded": True, "gpu_available": False, "gpu_name": "mock",
            "active_conversations": len(conversations)}


@app.post("/conversations")
def create():
    cid = str(uuid.uuid4())
    conversations[cid] = {}
    return {"conversation_id": cid, "status": "created"}


@app.delete("/conversations/{conversation_id}")
def end(conversation_id: str):
    conversations.pop(conversation_id, None)
    return {"conversation_id": conversation_id, "status": "ended"}


@app.post("/conversations/{conversation_id}/speakers")
async def register(conversation_id: str, speaker_id: str = Form(..., min_length=1, max_length=100),
                   audio_file: UploadFile = ...):
    mem = memory(conversation_id)
    audio = load(await audio_file.read())
    duration = len(audio) / RATE
    if not 4.5 <= duration <= 5.5:
        raise HTTPException(400, f"recording must be 4.5-5.5 s, got {duration:.2f}s")
    mask = speech_mask(audio)
    speech = float(mask.sum() * FRAME / RATE)
    if speech < 3.0:
        raise HTTPException(400, f"need at least 3 s of speech, detected {speech:.1f}s")
    mem[speaker_id] = embed(audio[: len(mask) * FRAME][np.repeat(mask, FRAME)])  # speech frames only
    return {"conversation_id": conversation_id, "speaker_id": speaker_id, "status": "registered",
            "recording_duration": round(duration, 2), "speech_duration": round(speech, 2)}


@app.post("/conversations/{conversation_id}/chunks")
async def chunks(conversation_id: str, audio_file: UploadFile):
    mem = memory(conversation_id)
    audio = load(await audio_file.read())
    if len(audio) > 10 * RATE:
        raise HTTPException(400, "chunk longer than 10 s")
    segments = []
    for a, b in regions(speech_mask(audio)):
        seg = audio[a * FRAME : b * FRAME]
        speaker, sim = "unknown", None
        if mem and len(seg) >= RATE:  # like the real service: < 1 s is too short to identify
            e = embed(seg)
            best = max(mem, key=lambda k: float(mem[k] @ e))
            sim = round(float(mem[best] @ e), 3)
            speaker = best if sim >= THRESHOLD else "unknown"
        start, end = a * FRAME / RATE, b * FRAME / RATE
        segments.append({
            "segment_id": str(uuid.uuid4()), "speaker_id": speaker, "similarity": sim,
            "start": round(start, 3), "end": round(end, 3), "duration": round(end - start, 3),
            "stream_index": 0, "source": "mock", "sample_rate": RATE, "audio_format": "wav",
            "audio_wav_base64": wav_b64(seg),
        })
    return {"conversation_id": conversation_id, "chunk_duration": round(len(audio) / RATE, 3),
            "segment_count": len(segments), "segments": segments}
