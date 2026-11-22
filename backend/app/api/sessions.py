"""REST: create/end a session, voice check-in, transcript log."""

import uuid
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Request, UploadFile

from ..schemas import Participant, SessionCreated, Utterance
from ..services.audio_service import AudioServiceError  # used by create_session
from ..services.audio_utils import decode_any, fit_duration, to_wav_bytes
from ..session import Session, SessionManager

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

CHECKIN_SECONDS = 5.0  # the recording is padded/trimmed to exactly this length


def manager(request: Request) -> SessionManager:
    return request.app.state.sessions


def get_session(request: Request, session_id: str) -> Session:
    session = manager(request).get(session_id)
    if session is None:
        raise HTTPException(404, "session not found")
    return session


@router.post("", response_model=SessionCreated)
async def create_session(request: Request):
    try:
        session = await manager(request).create()
    except AudioServiceError as e:
        raise HTTPException(502, str(e))
    return SessionCreated(session_id=session.id)


@router.delete("/{session_id}")
async def end_session(request: Request, session_id: str):
    if not await manager(request).end(session_id):
        raise HTTPException(404, "session not found")
    return {"session_id": session_id, "status": "ended"}


@router.post("/{session_id}/participants", response_model=Participant)
async def check_in(
    request: Request,
    session_id: str,
    name: str = Form(..., min_length=1, max_length=40),
    language: str = Form(..., min_length=2, max_length=10),
    audio_file: UploadFile = ...,
):
    """Voice check-in: ~5 s voice sample + preferred language. Assigns the participant a color slot."""
    session = get_session(request, session_id)
    slot = session.free_slot()
    if slot is None:
        raise HTTPException(409, "session is full (max 4 participants)")

    rate = session.services.settings.sample_rate
    raw = await audio_file.read()
    try:
        audio = decode_any(raw, rate)
    except Exception as e:
        raise HTTPException(400, f"could not decode audio: {e}")

    participant = Participant(id=f"p{slot}-{uuid.uuid4().hex[:6]}", name=name, language=language, slot=slot)
    sample = fit_duration(audio, rate, CHECKIN_SECONDS)
    # Only save the recording as files in the project. The voice is NOT sent to the
    # speaker-ID audio service yet; to enable recognition later, call:
    #   await session.services.audio.register_speaker(session.conversation_id, participant.id, sample)
    save_voice_sample(session, participant, raw, audio_file.filename, to_wav_bytes(sample, rate))
    await session.add_participant(participant)
    return participant


def save_voice_sample(session: Session, p: Participant, raw: bytes, filename: str | None, wav: bytes) -> None:
    """Keep the check-in recording on disk: voice_samples/<session>/<participant>.<ext> (as uploaded)
    and <participant>.wav (16 kHz mono, exactly 5 s: the format the speaker-ID model expects)."""
    folder = session.services.settings.voice_samples_dir / session.id
    folder.mkdir(parents=True, exist_ok=True)
    ext = Path(filename or "").suffix.lower() or ".bin"
    if ext != ".wav":  # don't overwrite the normalized WAV with the upload
        (folder / f"{p.id}{ext}").write_bytes(raw)
    (folder / f"{p.id}.wav").write_bytes(wav)


@router.post("/{session_id}/chunks")
async def save_chunk(
    request: Request,
    session_id: str,
    index: int = Form(..., ge=0),
    start: float = Form(..., ge=0),
    end: float = Form(..., ge=0),
    audio_file: UploadFile = ...,
):
    """Save one mic chunk (5 s .wav, a new one every 3 s) as
    voice_samples/<session>/chunks/chunk_<index>_<start>-<end>s.wav. No processing."""
    session = get_session(request, session_id)
    folder = session.services.settings.voice_samples_dir / session.id / "chunks"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"chunk_{index:04d}_{start:.1f}-{end:.1f}s.wav"
    path.write_bytes(await audio_file.read())
    return {"saved": path.name, "bytes": path.stat().st_size}


@router.delete("/{session_id}/participants/{participant_id}")
async def remove_participant(request: Request, session_id: str, participant_id: str):
    await get_session(request, session_id).remove_participant(participant_id)
    return {"participant_id": participant_id, "status": "removed"}


@router.get("/{session_id}/transcript", response_model=list[Utterance])
async def transcript(request: Request, session_id: str):
    """Full conversation history (finalized messages only)."""
    session = get_session(request, session_id)
    return [u for u in session.utterances.values() if u.status == "final"]
