"""REST: create/end a session, voice check-in, transcript log."""

import uuid

from fastapi import APIRouter, Form, HTTPException, Request, UploadFile

from ..schemas import Participant, SessionCreated, Utterance
from ..services.audio_service import AudioServiceError
from ..services.audio_utils import decode_any, fit_duration
from ..session import Session, SessionManager

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

CHECKIN_SECONDS = 5.0  # the audio service accepts 4.5-5.5 s
CHECKIN_MIN_SECONDS = 4.5


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
    try:
        audio = decode_any(await audio_file.read(), rate)
    except Exception as e:
        raise HTTPException(400, f"could not decode audio: {e}")
    if len(audio) < CHECKIN_MIN_SECONDS * rate:
        raise HTTPException(400, f"voice sample too short ({len(audio) / rate:.1f}s), record about 5 seconds")

    participant = Participant(id=f"p{slot}-{uuid.uuid4().hex[:6]}", name=name, language=language, slot=slot)
    try:
        await session.services.audio.register_speaker(
            session.conversation_id, participant.id, fit_duration(audio, rate, CHECKIN_SECONDS))
    except AudioServiceError as e:
        raise HTTPException(422, f"voice check-in failed: {e}")
    await session.add_participant(participant)
    return participant


@router.delete("/{session_id}/participants/{participant_id}")
async def remove_participant(request: Request, session_id: str, participant_id: str):
    await get_session(request, session_id).remove_participant(participant_id)
    return {"participant_id": participant_id, "status": "removed"}


@router.get("/{session_id}/transcript", response_model=list[Utterance])
async def transcript(request: Request, session_id: str):
    """Full conversation history (finalized messages only)."""
    session = get_session(request, session_id)
    return [u for u in session.utterances.values() if u.status == "final"]
