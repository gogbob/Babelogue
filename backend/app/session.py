"""In-memory conversation state and the per-session audio pipeline.

Everything lives in RAM in one process: run uvicorn with a single worker.

    WAV chunks from the browser (5 s every 3 s) ─▶ ChunkCoordinator (coordinator.py)
            ─▶ audio service (VAD + separation + speaker ID) ─▶ UtteranceBuilder
            ─▶ live bubble (partial STT) ─▶ final: STT (Groq / Whisper) + language ID
            ─▶ translate once per distinct preferred language ─▶ broadcast to every client
"""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field

from fastapi import WebSocket
from pydantic import BaseModel

from .config import Settings
from .schemas import (
    ErrorOut, Participant, ParticipantJoinedOut, ParticipantLeftOut, SessionStateOut, Utterance,
    UtteranceDiscardedOut, UtteranceFinalOut, UtterancePartialOut, UtteranceUpdatedOut,
)
from .services.audio_service import AudioServiceClient, AudioServiceError
from .coordinator import ChunkCoordinator
from .services.chunker import Chunk
from .services.transcriber import Transcriber
from .services.translator import TranslationService
from .services.tts import AzureTTS
from .services.utterances import UNKNOWN, OpenUtterance, UtteranceBuilder

log = logging.getLogger(__name__)


def now_ms() -> float:
    return time.time() * 1000


@dataclass
class Services:
    """Long-lived clients and models, created once at startup."""
    settings: Settings
    audio: AudioServiceClient
    transcriber: Transcriber
    translator: TranslationService
    tts: AzureTTS


@dataclass
class Session:
    id: str
    conversation_id: str  # id of the matching conversation on the audio service
    services: Services
    participants: dict[str, Participant] = field(default_factory=dict)
    utterances: dict[str, Utterance] = field(default_factory=dict)  # insertion order = transcript order
    clients: set[WebSocket] = field(default_factory=set)

    def __post_init__(self) -> None:
        s = self.services.settings
        self.coordinator = ChunkCoordinator(self)  # WAV chunks from the WebSocket -> this pipeline
        self.builder = UtteranceBuilder(s.sample_rate, s.merge_gap_s, s.finalize_silence_s, s.min_utterance_s)
        self._queue: asyncio.Queue[Chunk | None] = asyncio.Queue()
        self._worker = asyncio.create_task(self._run_chunks())
        self._tasks: set[asyncio.Task] = set()
        self._closed: set[str] = set()  # utterance ids already finalizing/finalized
        self._partial_busy: set[str] = set()  # utterance ids with a partial transcription running

    # ---------- participants ----------

    def free_slot(self) -> int | None:
        used = {p.slot for p in self.participants.values()}
        return next((i for i in range(1, self.services.settings.max_participants + 1) if i not in used), None)

    async def add_participant(self, p: Participant) -> None:
        self.participants[p.id] = p
        await self.broadcast(ParticipantJoinedOut(participant=p))

    async def remove_participant(self, pid: str) -> None:
        if self.participants.pop(pid, None):
            await self.broadcast(ParticipantLeftOut(participant_id=pid))

    def target_languages(self) -> set[str]:
        return {p.language for p in self.participants.values()}

    # ---------- clients ----------

    def state(self) -> SessionStateOut:
        return SessionStateOut(session_id=self.id, participants=list(self.participants.values()),
                               utterances=list(self.utterances.values()))

    async def broadcast(self, msg: BaseModel) -> None:
        data = msg.model_dump_json()
        for ws in list(self.clients):
            try:
                await ws.send_text(data)
            except Exception:
                self.clients.discard(ws)

    # ---------- audio in ----------

    def enqueue_chunk(self, chunk: Chunk | None) -> None:
        """Queue a chunk for the GPU. None = mic stopped: close all open bubbles."""
        self._queue.put_nowait(chunk)

    async def _run_chunks(self) -> None:
        """Process chunks one at a time, in order (the audio service serializes inference anyway)."""
        while True:
            chunk = await self._queue.get()
            try:
                if chunk is None:
                    for utt in self.builder.flush():
                        self._spawn(self._finalize(utt))
                    continue
                segments = await self.services.audio.process_chunk(self.conversation_id, chunk.audio)
                still_open, closed = self.builder.ingest(chunk, segments)
                for utt in closed:
                    self._spawn(self._finalize(utt))
                for utt in still_open:
                    self._spawn(self._partial(utt))
            except AudioServiceError as e:
                log.warning("chunk failed: %s", e)
                await self.broadcast(ErrorOut(message=str(e)))
            except Exception:
                log.exception("chunk processing crashed")

    # ---------- utterances ----------

    def _participant_of(self, utt: OpenUtterance) -> str | None:
        return utt.speaker_id if utt.speaker_id != UNKNOWN and utt.speaker_id in self.participants else None

    async def _partial(self, utt: OpenUtterance) -> None:
        if utt.id in self._partial_busy:
            return  # Whisper is behind: skip this update rather than queueing a stale one
        text = ""
        if self.services.settings.partial_transcripts:
            self._partial_busy.add(utt.id)
            try:
                text = (await self.services.transcriber.transcribe(utt.audio, partial=True)).text
            finally:
                self._partial_busy.discard(utt.id)
        if utt.id in self._closed:
            return  # finalization overtook this partial
        u = Utterance(id=utt.id, participant_id=self._participant_of(utt), status="live", source="voice",
                      text=text, start=utt.start, end=utt.end,
                      created_at=self.utterances[utt.id].created_at if utt.id in self.utterances else now_ms())
        self.utterances[utt.id] = u
        await self.broadcast(UtterancePartialOut(utterance=u))

    async def _finalize(self, utt: OpenUtterance) -> None:
        self._closed.add(utt.id)
        tr = await self.services.transcriber.transcribe(utt.audio)
        if not tr.text:
            if self.utterances.pop(utt.id, None) is not None:
                await self.broadcast(UtteranceDiscardedOut(utterance_id=utt.id))
            return
        pid = self._participant_of(utt)
        source = tr.language or (self.participants[pid].language if pid else "en")
        translations = await self._translate(tr.text, source)
        created = self.utterances[utt.id].created_at if utt.id in self.utterances else now_ms()
        u = Utterance(id=utt.id, participant_id=pid, status="final", source="voice", text=tr.text,
                      source_language=source, translations=translations, start=utt.start, end=utt.end,
                      created_at=created)
        self.utterances[utt.id] = u
        await self.broadcast(UtteranceFinalOut(utterance=u))

    async def _translate(self, text: str, source: str) -> dict[str, str]:
        try:
            return await self.services.translator.translate_many(text, source, self.target_languages())
        except Exception as e:
            log.exception("translation failed")
            await self.broadcast(ErrorOut(message=f"translation failed: {e}"))
            return {source: text}

    async def add_text_message(self, participant_id: str, text: str) -> None:
        """Typing fallback: same translate -> display flow as speech."""
        p = self.participants.get(participant_id)
        if p is None:
            await self.broadcast(ErrorOut(message=f"unknown participant {participant_id}"))
            return
        translations = await self._translate(text, p.language)
        u = Utterance(id=uuid.uuid4().hex, participant_id=p.id, status="final", source="text", text=text,
                      source_language=p.language, translations=translations, created_at=now_ms())
        self.utterances[u.id] = u
        await self.broadcast(UtteranceFinalOut(utterance=u))

    async def reassign(self, utterance_id: str, participant_id: str) -> None:
        """Manual one-tap fix when speaker ID got it wrong."""
        u = self.utterances.get(utterance_id)
        if u is None or participant_id not in self.participants:
            await self.broadcast(ErrorOut(message="cannot reassign: unknown utterance or participant"))
            return
        u.participant_id = participant_id
        # Keep a still-open bubble on the new speaker too.
        for spk, open_utt in list(self.builder.open.items()):
            if open_utt.id == utterance_id and spk != participant_id:
                del self.builder.open[spk]
                open_utt.speaker_id = participant_id
                self.builder.open.setdefault(participant_id, open_utt)
        await self.broadcast(UtteranceUpdatedOut(utterance=u))

    # ---------- lifecycle ----------

    def _spawn(self, coro) -> None:
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._task_done)

    def _task_done(self, task: asyncio.Task) -> None:
        self._tasks.discard(task)
        if not task.cancelled() and task.exception() is not None:
            log.error("utterance task failed", exc_info=task.exception())

    async def close(self) -> None:
        self._worker.cancel()
        for t in list(self._tasks):
            t.cancel()
        for ws in list(self.clients):
            await ws.close()
        await self.services.audio.end_conversation(self.conversation_id)


class SessionManager:
    def __init__(self, services: Services):
        self.services = services
        self.sessions: dict[str, Session] = {}

    async def create(self) -> Session:
        conversation_id = await self.services.audio.create_conversation()
        session = Session(id=uuid.uuid4().hex[:8], conversation_id=conversation_id, services=self.services)
        self.sessions[session.id] = session
        return session

    def get(self, session_id: str) -> Session | None:
        return self.sessions.get(session_id)

    async def end(self, session_id: str) -> bool:
        session = self.sessions.pop(session_id, None)
        if session is None:
            return False
        await session.close()
        return True

    async def close_all(self) -> None:
        for sid in list(self.sessions):
            await self.end(sid)
