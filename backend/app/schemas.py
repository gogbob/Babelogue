"""Wire format shared with the frontend. Mirror of frontend/src/api/protocol.ts: keep both in sync.

WebSocket  /ws/{session_id}
  client -> server
    * binary frames: one WAV chunk each (5 s, 16 kHz mono) with a small JSON header,
      see coordinator.py for the exact layout
    * JSON text frames: ClientMessage below ({"type": "flush"} when the mic turns off)
  server -> client
    * JSON text frames: ServerMessage below
"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field

SpeakerSlot = Literal[1, 2, 3, 4]  # decides the color (1 red, 2 blue, 3 yellow, 4 green)


# ---------- domain objects ----------

class Participant(BaseModel):
    id: str
    name: str
    language: str  # preferred language, ISO 639-1 (e.g. "fr")
    slot: SpeakerSlot


class Utterance(BaseModel):
    id: str
    participant_id: str | None  # None = speaker not recognised yet (can be reassigned)
    status: Literal["live", "final"]
    source: Literal["voice", "text"]
    text: str  # original text in the source language
    source_language: str | None = None  # detected (voice) or the typer's language (text)
    translations: dict[str, str] = {}  # target language -> translated text
    start: float | None = None  # seconds since session start (voice only)
    end: float | None = None
    created_at: float  # unix ms


# ---------- client -> server ----------

class TextMessageIn(BaseModel):
    type: Literal["text_message"]
    participant_id: str
    text: str = Field(min_length=1, max_length=2000)


class SpeakerReassignIn(BaseModel):
    type: Literal["speaker_reassign"]
    utterance_id: str
    participant_id: str


class FlushIn(BaseModel):
    """Mic turned off: process whatever audio is buffered and close open bubbles."""
    type: Literal["flush"]


ClientMessage = Annotated[TextMessageIn | SpeakerReassignIn | FlushIn, Field(discriminator="type")]


# ---------- server -> client ----------

class SessionStateOut(BaseModel):
    """Sent once on connect so a (re)connecting client can rebuild the screen."""
    type: Literal["session_state"] = "session_state"
    session_id: str
    participants: list[Participant]
    utterances: list[Utterance]


class ParticipantJoinedOut(BaseModel):
    type: Literal["participant_joined"] = "participant_joined"
    participant: Participant


class ParticipantLeftOut(BaseModel):
    type: Literal["participant_left"] = "participant_left"
    participant_id: str


class UtterancePartialOut(BaseModel):
    """Live bubble created or updated (no translation yet)."""
    type: Literal["utterance_partial"] = "utterance_partial"
    utterance: Utterance


class UtteranceFinalOut(BaseModel):
    """Bubble closed: final text, detected language, translations."""
    type: Literal["utterance_final"] = "utterance_final"
    utterance: Utterance


class UtteranceUpdatedOut(BaseModel):
    """An existing message changed (e.g. reassigned to another speaker)."""
    type: Literal["utterance_updated"] = "utterance_updated"
    utterance: Utterance


class UtteranceDiscardedOut(BaseModel):
    """A live bubble turned out to be noise (no text): remove it."""
    type: Literal["utterance_discarded"] = "utterance_discarded"
    utterance_id: str


class ErrorOut(BaseModel):
    type: Literal["error"] = "error"
    message: str


ServerMessage = (
    SessionStateOut | ParticipantJoinedOut | ParticipantLeftOut | UtterancePartialOut
    | UtteranceFinalOut | UtteranceUpdatedOut | UtteranceDiscardedOut | ErrorOut
)


# ---------- REST ----------

class SessionCreated(BaseModel):
    session_id: str


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    language: str
