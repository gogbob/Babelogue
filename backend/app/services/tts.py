"""Azure AI Speech text-to-speech, cached on disk by (text, language, voice) to spare the F0 quota."""

import asyncio
import hashlib
from html import escape

import httpx

from ..config import Settings

# Neural voice per preferred language. Extend alongside LANGUAGES in VoiceCalibration.tsx.
VOICES = {
    "en": ("en-US", "en-US-JennyNeural"),
    "fr": ("fr-FR", "fr-FR-DeniseNeural"),
    "es": ("es-ES", "es-ES-ElviraNeural"),
    "de": ("de-DE", "de-DE-KatjaNeural"),
    "zh": ("zh-CN", "zh-CN-XiaoxiaoNeural"),
    "ja": ("ja-JP", "ja-JP-NanamiNeural"),
    "ar": ("ar-SA", "ar-SA-ZariyahNeural"),
    "pt": ("pt-BR", "pt-BR-FranciscaNeural"),
}
OUTPUT_FORMAT = "audio-24khz-48kbitrate-mono-mp3"
MEDIA_TYPE = "audio/mpeg"


class TTSError(RuntimeError):
    pass


class AzureTTS:
    def __init__(self, settings: Settings):
        self._key = settings.azure_speech_key
        self._url = f"https://{settings.azure_speech_region}.tts.speech.microsoft.com/cognitiveservices/v1"
        self._cache = settings.tts_cache_dir
        self._cache.mkdir(parents=True, exist_ok=True)
        self._http = httpx.AsyncClient(timeout=15)
        self._locks: dict[str, asyncio.Lock] = {}  # avoid paying twice for a double click

    async def close(self) -> None:
        await self._http.aclose()

    async def synthesize(self, text: str, language: str) -> bytes:
        lang = language.split("-")[0].lower()
        if lang not in VOICES:
            raise TTSError(f"no voice configured for language '{language}'")
        locale, voice = VOICES[lang]
        key = hashlib.sha256(f"{voice}\n{text}".encode()).hexdigest()
        path = self._cache / f"{key}.mp3"
        if path.exists():
            return path.read_bytes()

        async with self._locks.setdefault(key, asyncio.Lock()):
            if path.exists():
                return path.read_bytes()
            if not self._key:
                raise TTSError("AZURE_SPEECH_KEY is not set")
            ssml = (
                f"<speak version='1.0' xml:lang='{locale}'>"
                f"<voice name='{voice}'>{escape(text)}</voice></speak>"
            )
            r = await self._http.post(self._url, content=ssml.encode(), headers={
                "Ocp-Apim-Subscription-Key": self._key,
                "Content-Type": "application/ssml+xml",
                "X-Microsoft-OutputFormat": OUTPUT_FORMAT,
                "User-Agent": "babelogue",
            })
            if r.status_code == 429:
                raise TTSError("Azure TTS rate limit reached (F0 tier), try again shortly")
            if r.status_code >= 400:
                raise TTSError(f"Azure TTS error {r.status_code}: {r.text[:200]}")
            path.write_bytes(r.content)
            return r.content
