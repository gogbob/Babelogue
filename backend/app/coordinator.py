"""Coordinator: receives the frontend's WAV chunks over the WebSocket and feeds the session pipeline.

    React mic ─▶ ChunkRecorder (5 s .wav every 3 s) ─WS binary─▶ ChunkCoordinator
        ─▶ save the .wav (voice_samples/<session>/chunks/)
        ─▶ Session queue ─▶ GPU audio service (separation + speaker ID against the calibration voices)
        ─▶ UtteranceBuilder ─▶ Groq STT ─▶ Azure Translator (every participant's language)
        ─▶ utterance_partial / utterance_final broadcast ─▶ React chat bubbles

Wire format of one chunk (a single binary WebSocket message):

    [ 4 bytes: header length N, uint32 little-endian ]
    [ N bytes: UTF-8 JSON {"index": 0, "start": 0.0, "end": 5.0} ]   seconds since the mic was turned on
    [ rest:    the .wav file (16 kHz mono 16-bit PCM) ]

Every mic run restarts at 0 s on the client. The coordinator shifts each run onto one continuous
session timeline, because the utterance builder relies on time only moving forward.
"""

import json
import logging
import struct
from typing import TYPE_CHECKING

from .services.audio_utils import from_wav_bytes
from .services.chunker import Chunk

if TYPE_CHECKING:
    from .session import Session

log = logging.getLogger(__name__)

MAX_HEADER = 1024  # bytes; the JSON header is ~50
RUN_GAP_S = 1.0  # spacing between two mic runs on the session timeline


class ChunkError(ValueError):
    """The binary message is not a valid chunk envelope."""


def parse_envelope(data: bytes) -> tuple[dict, bytes]:
    if len(data) < 4:
        raise ChunkError("message too short")
    (n,) = struct.unpack_from("<I", data, 0)
    if not 0 < n <= MAX_HEADER or len(data) < 4 + n:
        raise ChunkError("bad header length")
    try:
        meta = json.loads(data[4 : 4 + n].decode("utf-8"))
        meta = {"index": int(meta["index"]), "start": float(meta["start"]), "end": float(meta["end"])}
    except (ValueError, KeyError, TypeError) as e:
        raise ChunkError(f"bad header: {e}") from e
    return meta, data[4 + n :]


class ChunkCoordinator:
    def __init__(self, session: "Session"):
        self.session = session
        self._base = 0.0  # where the current mic run starts on the session timeline
        self._latest_end = 0.0  # end of the newest chunk on the session timeline
        self._saved = 0  # running file counter (client indexes restart every mic run)

    def handle(self, data: bytes) -> None:
        """One binary WebSocket message: decode, save, queue for the GPU."""
        meta, wav = parse_envelope(data)
        rate = self.session.services.settings.sample_rate
        try:
            audio = from_wav_bytes(wav, rate)
        except Exception as e:
            raise ChunkError(f"could not decode chunk {meta['index']}: {e}") from e

        offset = self._base + meta["start"]
        end = offset + len(audio) / rate
        self._latest_end = max(self._latest_end, end)
        self._save(wav, offset, end)
        self.session.enqueue_chunk(Chunk(audio=audio, offset=offset, end=end))

    def mic_stopped(self) -> None:
        """Mic turned off: close open bubbles; the next run continues after this one."""
        self.session.enqueue_chunk(None)
        self._base = self._latest_end + RUN_GAP_S

    def _save(self, wav: bytes, start: float, end: float) -> None:
        folder = self.session.services.settings.voice_samples_dir / self.session.id / "chunks"
        try:
            folder.mkdir(parents=True, exist_ok=True)
            (folder / f"chunk_{self._saved:04d}_{start:.1f}-{end:.1f}s.wav").write_bytes(wav)
        except OSError:
            log.exception("could not save chunk")  # saving is a side effect; keep processing
        self._saved += 1
