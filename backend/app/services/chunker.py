"""Cuts the continuous mic stream into overlapping chunks (5 s long, a new one every 2.5 s)."""

from dataclasses import dataclass

import numpy as np


@dataclass
class Chunk:
    audio: np.ndarray
    offset: float  # seconds since session start where this chunk begins
    end: float  # seconds since session start where this chunk ends


class Chunker:
    def __init__(self, sample_rate: int, chunk_seconds: float, hop_seconds: float):
        self.rate = sample_rate
        self.chunk_n = int(chunk_seconds * sample_rate)
        self.hop_n = int(hop_seconds * sample_rate)
        self._buf = np.zeros(0, dtype=np.float32)
        self._buf_start = 0  # absolute sample index of _buf[0]
        self._next_start = 0  # absolute sample index where the next chunk begins
        self._covered_end = 0  # absolute sample index up to which chunks have been emitted
        self.total = 0  # absolute samples received so far

    @property
    def now(self) -> float:
        return self.total / self.rate

    def push(self, audio: np.ndarray) -> list[Chunk]:
        """Add audio, return every chunk that is now complete."""
        self._buf = np.concatenate([self._buf, audio])
        self.total += len(audio)
        chunks = []
        while self.total - self._next_start >= self.chunk_n:
            chunks.append(self._take(self._next_start, self._next_start + self.chunk_n))
            self._next_start += self.hop_n
        self._trim()
        return chunks

    def flush(self) -> Chunk | None:
        """Mic stopped: return a chunk ending now if some audio was never sent, then restart the grid."""
        chunk = None
        if self.total > self._covered_end:
            chunk = self._take(max(self._buf_start, self.total - self.chunk_n), self.total)
        self._next_start = self.total
        self._trim()
        return chunk

    def _take(self, start: int, stop: int) -> Chunk:
        self._covered_end = max(self._covered_end, stop)
        a, b = start - self._buf_start, stop - self._buf_start
        return Chunk(audio=self._buf[a:b].copy(), offset=start / self.rate, end=stop / self.rate)

    def _trim(self) -> None:
        # Keep everything the next chunk needs, plus one chunk of history for flush().
        keep_from = min(self._next_start, max(0, self.total - self.chunk_n))
        drop = keep_from - self._buf_start
        if drop > 0:
            self._buf = self._buf[drop:]
            self._buf_start += drop
