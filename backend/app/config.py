"""All runtime settings, read from environment variables or backend/.env."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    # --- Audio processing service (the GPU box, see API_PCGPU.md) ---
    audio_service_url: str = "http://localhost:8001"
    audio_service_timeout_s: float = 30.0

    # --- Audio format: one fixed format end to end ---
    sample_rate: int = 16_000  # Hz, mono
    chunk_seconds: float = 5.0  # chunk length sent to the audio service
    hop_seconds: float = 3  # a new chunk starts every hop (3 s overlap)
    max_participants: int = 4

    # --- Utterance building ---
    merge_gap_s: float = 0.8  # same-speaker segments closer than this join one utterance
    finalize_silence_s: float = 0.7  # utterance closes when it stops this far before the newest audio
    min_utterance_s: float = 0.4  # shorter utterances are dropped as noise

    # --- Speech-to-text ---
    stt_backend: Literal["faster_whisper", "dummy", "groq"] = "dummy"
    groq_api_key: str = ""
    groq_model: str = "whisper-large-v3-turbo"
    whisper_model: str = "small"  # tiny | base | small | medium | large-v3 | distil-large-v3
    whisper_device: str = "auto"  # auto | cuda | cpu
    whisper_compute_type: str = "int8"  # int8 | int8_float16 | float16
    partial_transcripts: bool = True  # re-run Whisper on open utterances for live bubbles

    # --- Translation: Azure AI Translator (echo = no-op for development without Azure) ---
    translator_backend: Literal["azure", "echo"] = "azure"
    azure_translator_key: str = ""
    azure_translator_region: str = ""  # e.g. canadaeast; required for regional / multi-service keys
    azure_translator_endpoint: str = "https://api.cognitive.microsofttranslator.com"
    azure_translator_timeout_s: float = 10.0

    # --- Azure AI Speech (TTS) ---
    azure_speech_key: str = ""
    azure_speech_region: str = ""
    tts_cache_dir: Path = BACKEND_DIR / "tts_cache"
    voice_samples_dir: Path = BACKEND_DIR / "voice_samples"  # saved voice check-in recordings

    # --- Server ---
    cors_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
