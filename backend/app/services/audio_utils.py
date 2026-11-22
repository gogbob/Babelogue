"""Audio conversions. Internally all audio is float32 mono numpy at settings.sample_rate (16 kHz)."""

import io
from math import gcd

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly


def pcm16_to_float(data: bytes) -> np.ndarray:
    """Raw 16-bit little-endian PCM (what the browser streams over the WebSocket) -> float32."""
    return np.frombuffer(data, dtype="<i2").astype(np.float32) / 32768.0


def resample(audio: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    if src_rate == dst_rate:
        return audio
    g = gcd(src_rate, dst_rate)
    return resample_poly(audio, dst_rate // g, src_rate // g).astype(np.float32)


def decode_any(data: bytes, target_rate: int) -> np.ndarray:
    """Decode an uploaded file to mono float32 at target_rate.

    WAV/FLAC/OGG go through SoundFile. Anything else (e.g. the webm/opus that the browser's
    MediaRecorder produces) goes through PyAV, which bundles ffmpeg.
    """
    try:
        audio, rate = sf.read(io.BytesIO(data), dtype="float32", always_2d=True)
        audio = audio.mean(axis=1)
    except sf.LibsndfileError:
        audio, rate = _decode_with_av(data)
    return resample(audio, rate, target_rate)


def _decode_with_av(data: bytes) -> tuple[np.ndarray, int]:
    import av  # imported lazily: only needed for compressed browser uploads

    with av.open(io.BytesIO(data)) as container:
        stream = container.streams.audio[0]
        resampler = av.AudioResampler(format="flt", layout="mono", rate=stream.rate or 48_000)
        parts = []
        for frame in container.decode(stream):
            for out in resampler.resample(frame):
                parts.append(out.to_ndarray().reshape(-1))
        for out in resampler.resample(None):  # flush
            parts.append(out.to_ndarray().reshape(-1))
    audio = np.concatenate(parts) if parts else np.zeros(0, dtype=np.float32)
    return audio.astype(np.float32), resampler.rate


def to_wav_bytes(audio: np.ndarray, rate: int) -> bytes:
    """float32 mono -> 16-bit PCM WAV, the format the audio service expects."""
    buf = io.BytesIO()
    sf.write(buf, np.clip(audio, -1.0, 1.0), rate, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def from_wav_bytes(data: bytes, target_rate: int) -> np.ndarray:
    audio, rate = sf.read(io.BytesIO(data), dtype="float32", always_2d=True)
    return resample(audio.mean(axis=1), rate, target_rate)


def fit_duration(audio: np.ndarray, rate: int, seconds: float) -> np.ndarray:
    """Trim or zero-pad to exactly `seconds` (voice check-in must be 4.5-5.5 s)."""
    n = int(round(seconds * rate))
    if len(audio) >= n:
        return audio[:n]
    return np.pad(audio, (0, n - len(audio)))
