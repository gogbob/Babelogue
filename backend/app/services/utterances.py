"""Turns per-chunk segments from the audio service into live/final utterances.

Chunks overlap (5 s chunks every 2.5 s), so the same speech is reported twice. This module:
  * maps chunk-relative times onto the session timeline,
  * merges a speaker's consecutive segments into one open utterance (the live bubble),
  * ignores speech that was already finalized (overlap duplicates),
  * lets a recognised label take over an "unknown" bubble covering the same speech,
  * closes an utterance once the newest chunk shows the speaker went quiet.
"""

import uuid
from dataclasses import dataclass, field

import numpy as np

from .audio_service import Segment
from .chunker import Chunk

UNKNOWN = "unknown"


@dataclass
class OpenUtterance:
    id: str
    speaker_id: str  # audio-service speaker id (= participant id) or UNKNOWN
    start: float
    end: float
    rate: int
    _start_sample: int = 0
    _audio: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=np.float32))

    def __post_init__(self) -> None:
        self._start_sample = int(self.start * self.rate)

    @property
    def audio(self) -> np.ndarray:
        return self._audio

    @property
    def duration(self) -> float:
        return self.end - self.start

    def paste(self, g_start: float, audio: np.ndarray) -> None:
        """Write audio at its global position. Overlapping audio from a newer chunk overwrites older."""
        s = int(round(g_start * self.rate))
        if s < self._start_sample:  # grow to the left
            self._audio = np.concatenate([np.zeros(self._start_sample - s, np.float32), self._audio])
            self._start_sample = s
        i = s - self._start_sample
        need = i + len(audio)
        if need > len(self._audio):
            self._audio = np.pad(self._audio, (0, need - len(self._audio)))
        self._audio[i:need] = audio
        self.start = min(self.start, g_start)
        self.end = max(self.end, g_start + len(audio) / self.rate)


def _overlap(a0: float, a1: float, b0: float, b1: float) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


class UtteranceBuilder:
    def __init__(self, rate: int, merge_gap_s: float, finalize_silence_s: float, min_utterance_s: float):
        self.rate = rate
        self.merge_gap = merge_gap_s
        self.finalize_silence = finalize_silence_s
        self.min_dur = min_utterance_s
        self.open: dict[str, OpenUtterance] = {}  # speaker_id -> open utterance
        self._final_until: dict[str, float] = {}  # speaker_id -> end of their last final utterance
        self._recent_final: list[tuple[float, float, str]] = []  # (start, end, speaker) already finalized

    def ingest(self, chunk: Chunk, segments: list[Segment]) -> tuple[list[OpenUtterance], list[OpenUtterance]]:
        """Returns (utterances still open that changed, utterances that just closed)."""
        changed: dict[str, OpenUtterance] = {}
        closed: list[OpenUtterance] = []

        for seg in sorted(segments, key=lambda s: s.start):
            g0, g1 = chunk.offset + seg.start, chunk.offset + seg.end
            audio = seg.audio

            # Drop the part of the segment this speaker already said in a finalized utterance.
            # Unknown speech also skips anything finalized by anyone; known speech skips finalized unknowns.
            done = self._final_until.get(seg.speaker_id, 0.0)
            for s0, s1, spk in self._recent_final:
                if s0 < g1 and (seg.speaker_id == UNKNOWN or spk == UNKNOWN):
                    done = max(done, s1)
            if g1 <= done + 0.05:
                continue
            if g0 < done:
                audio = audio[int((done - g0) * self.rate):]
                g0 = done

            utt = self._match_open(seg.speaker_id, g0, g1)
            if utt is None:
                # This speaker starts a new utterance; their previous one (if any) is over.
                if (prev := self.open.pop(seg.speaker_id, None)) is not None:
                    closed.append(self._close(prev))
                    changed.pop(prev.id, None)
                utt = OpenUtterance(id=uuid.uuid4().hex, speaker_id=seg.speaker_id, start=g0, end=g0, rate=self.rate)
                self.open[seg.speaker_id] = utt
            utt.paste(g0, audio)
            changed[utt.id] = utt

        # Close utterances whose speaker has been quiet for a while at the end of this chunk.
        for spk, utt in list(self.open.items()):
            if utt.end < chunk.end - self.finalize_silence:
                del self.open[spk]
                closed.append(self._close(utt))
                changed.pop(utt.id, None)

        return list(changed.values()), [u for u in closed if u.duration >= self.min_dur]

    def flush(self) -> list[OpenUtterance]:
        """Mic stopped: close everything."""
        closed = [self._close(u) for u in self.open.values()]
        self.open.clear()
        return [u for u in closed if u.duration >= self.min_dur]

    def _match_open(self, speaker_id: str, g0: float, g1: float) -> OpenUtterance | None:
        utt = self.open.get(speaker_id)
        if utt is not None and g0 <= utt.end + self.merge_gap:
            return utt
        if speaker_id == UNKNOWN:
            # Unlabelled speech overlapping a recognised speaker's bubble belongs to that bubble.
            for u in self.open.values():
                if u.speaker_id != UNKNOWN and _overlap(g0, g1, u.start, u.end + self.merge_gap) > 0:
                    return u
        else:
            # A recognised label takes over an unknown bubble covering the same speech (same id, new color).
            unk = self.open.get(UNKNOWN)
            if unk is not None and _overlap(g0, g1, unk.start, unk.end + self.merge_gap) > 0:
                del self.open[UNKNOWN]
                if utt is not None:  # speaker already had a bubble: merge into it
                    utt.paste(unk.start, unk.audio)
                    return utt
                unk.speaker_id = speaker_id
                self.open[speaker_id] = unk
                return unk
        return None

    def _close(self, utt: OpenUtterance) -> OpenUtterance:
        self._final_until[utt.speaker_id] = max(self._final_until.get(utt.speaker_id, 0.0), utt.end)
        self._recent_final = (self._recent_final + [(utt.start, utt.end, utt.speaker_id)])[-20:]
        return utt
