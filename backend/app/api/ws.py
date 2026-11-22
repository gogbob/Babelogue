"""WebSocket /ws/{session_id}: audio up (binary PCM16), chat events down (JSON). See schemas.py."""

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import TypeAdapter, ValidationError

from ..schemas import ClientMessage, ErrorOut, FlushIn, SpeakerReassignIn, TextMessageIn
from ..services.audio_utils import pcm16_to_float

router = APIRouter()
log = logging.getLogger(__name__)
_client_message = TypeAdapter(ClientMessage)


@router.websocket("/ws/{session_id}")
async def session_socket(ws: WebSocket, session_id: str):
    session = ws.app.state.sessions.get(session_id)
    if session is None:
        await ws.close(code=4404, reason="session not found")
        return

    await ws.accept()
    session.clients.add(ws)
    await ws.send_text(session.state().model_dump_json())
    try:
        while True:
            frame = await ws.receive()
            if frame["type"] == "websocket.disconnect":
                break
            if (data := frame.get("bytes")) is not None:
                session.push_audio(pcm16_to_float(data))
            elif (text := frame.get("text")) is not None:
                try:
                    msg = _client_message.validate_json(text)
                except ValidationError as e:
                    await ws.send_text(ErrorOut(message=f"bad message: {e.errors()[0]['msg']}").model_dump_json())
                    continue
                if isinstance(msg, TextMessageIn):
                    await session.add_text_message(msg.participant_id, msg.text)
                elif isinstance(msg, SpeakerReassignIn):
                    await session.reassign(msg.utterance_id, msg.participant_id)
                elif isinstance(msg, FlushIn):
                    session.flush_audio()
    except WebSocketDisconnect:
        pass
    finally:
        session.clients.discard(ws)
