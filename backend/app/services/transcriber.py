"""Speech-to-text + language ID with faster-whisper. Loaded once at startup."""

import asyncio
import logging
import threading
from dataclasses import dataclass

import numpy as np

from ..config import Settings

log = logging.getLogger(__name__)


@dataclass
class Transcript:
    text: str
    language: str | None  # ISO 639-1, e.g. "fr"
    language_probability: float | None = None


class Transcriber:
    async def transcribe(self, audio: np.ndarray, *, partial: bool = False, language: str | None = None) -> Transcript:
        raise NotImplementedError


class WhisperTranscriber(Transcriber):
    def __init__(self, settings: Settings):
        from faster_whisper import WhisperModel

        log.info("loading faster-whisper %s (%s, %s)", settings.whisper_model, settings.whisper_device,
                 settings.whisper_compute_type)
        self._model = WhisperModel(settings.whisper_model, device=settings.whisper_device,
                                   compute_type=settings.whisper_compute_type)
        self._lock = threading.Lock()  # one model instance: run one inference at a time

    async def transcribe(self, audio: np.ndarray, *, partial: bool = False, language: str | None = None) -> Transcript:
        return await asyncio.to_thread(self._run, audio, partial, language)

    def _run(self, audio: np.ndarray, partial: bool, language: str | None) -> Transcript:
        with self._lock:
            segments, info = self._model.transcribe(
                audio,
                language=language,
                beam_size=1 if partial else 5,  # partials favour speed
                vad_filter=False,  # the audio service already did VAD
                condition_on_previous_text=False,
            )
            text = " ".join(s.text.strip() for s in segments).strip()
        return Transcript(text=text, language=info.language, language_probability=info.language_probability)


class DummyTranscriber(Transcriber):
    """For running the pipeline without ML dependencies."""

    async def transcribe(self, audio: np.ndarray, *, partial: bool = False, language: str | None = None) -> Transcript:
        secs = len(audio) / 16_000
        return Transcript(text=f"[{secs:.1f}s of speech{'…' if partial else ''}]", language=language or "en")


def build_transcriber(settings: Settings) -> Transcriber:
    if settings.stt_backend == "dummy":
        return DummyTranscriber()
    return WhisperTranscriber(settings)
