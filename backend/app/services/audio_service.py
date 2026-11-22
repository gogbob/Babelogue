"""HTTP client for the audio processing service (VAD + separation + speaker ID on the GPU box).

Contract: API_PCGPU.md at the repo root.
"""

import base64
from dataclasses import dataclass

import httpx
import numpy as np

from .audio_utils import from_wav_bytes, to_wav_bytes


class AudioServiceError(RuntimeError):
    pass


@dataclass
class Segment:
    """One separated speech segment. start/end are relative to the submitted chunk."""
    speaker_id: str  # registered speaker id, or "unknown"
    similarity: float | None
    start: float
    end: float
    stream_index: int
    audio: np.ndarray  # float32 mono at our sample rate


class AudioServiceClient:
    def __init__(self, base_url: str, sample_rate: int, timeout_s: float):
        self.sample_rate = sample_rate
        self._http = httpx.AsyncClient(base_url=base_url, timeout=timeout_s)

    async def close(self) -> None:
        await self._http.aclose()

    async def health(self) -> dict:
        r = await self._http.get("/health")
        r.raise_for_status()
        return r.json()

    async def create_conversation(self) -> str:
        r = await self._post("/conversations")
        return r["conversation_id"]

    async def end_conversation(self, conversation_id: str) -> None:
        try:
            await self._http.delete(f"/conversations/{conversation_id}")
        except httpx.HTTPError:
            pass  # best effort: memory on the GPU box is temporary anyway

    async def register_speaker(self, conversation_id: str, speaker_id: str, audio: np.ndarray) -> dict:
        """audio: ~5 s of the participant's voice. Returns recording/speech durations."""
        return await self._post(
            f"/conversations/{conversation_id}/speakers",
            data={"speaker_id": speaker_id},
            files={"audio_file": ("checkin.wav", to_wav_bytes(audio, self.sample_rate), "audio/wav")},
        )

    async def process_chunk(self, conversation_id: str, audio: np.ndarray) -> list[Segment]:
        """audio: up to 10 s. Returns the separated, speaker-labelled segments."""
        body = await self._post(
            f"/conversations/{conversation_id}/chunks",
            files={"audio_file": ("chunk.wav", to_wav_bytes(audio, self.sample_rate), "audio/wav")},
        )
        return [
            Segment(
                speaker_id=s["speaker_id"],
                similarity=s.get("similarity"),
                start=float(s["start"]),
                end=float(s["end"]),
                stream_index=int(s.get("stream_index", 0)),
                audio=from_wav_bytes(base64.b64decode(s["audio_wav_base64"]), self.sample_rate),
            )
            for s in body.get("segments", [])
        ]

    async def _post(self, path: str, **kwargs) -> dict:
        try:
            r = await self._http.post(path, **kwargs)
        except httpx.HTTPError as e:
            raise AudioServiceError(f"audio service unreachable: {e}") from e
        if r.status_code >= 400:
            try:
                detail = r.json().get("detail", r.text)
            except ValueError:
                detail = r.text
            raise AudioServiceError(f"audio service {r.status_code}: {detail}")
        return r.json()
