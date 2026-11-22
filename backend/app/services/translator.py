"""Translation of finalized utterances with Azure AI Translator.

Translate once per distinct target language, not once per listener. Azure accepts several
`to` languages in one request, so every utterance costs a single HTTP call no matter how
many languages the session has (see AzureTranslator.translate_many).
"""

import asyncio
import logging
import uuid

import httpx

from ..config import Settings

log = logging.getLogger(__name__)

# App language code (what Whisper detects / the UI sends) -> Azure Translator code.
# Anything not listed is passed through unchanged (en, fr, es, de, ja, ar, pt, ...).
_TO_AZURE = {"zh": "zh-Hans", "no": "nb", "sr": "sr-Cyrl", "jw": "jv"}
_FROM_AZURE = {v: k for k, v in _TO_AZURE.items()}


def _azure(code: str) -> str:
    return _TO_AZURE.get(code, code)


class Translator:
    name = "base"

    def __init__(self, settings: Settings | None = None):
        pass

    async def translate_many(self, text: str, source: str, targets: list[str]) -> dict[str, str]:
        """Translate `text` into every language in `targets` (source language excluded)."""
        raise NotImplementedError

    async def close(self) -> None:
        pass


class AzureTranslator(Translator):
    """Azure AI Translator REST API v3 (F0 tier: 2M characters/month)."""

    name = "azure"
    RETRIES = 2  # extra attempts on 429 / 5xx / network errors

    def __init__(self, settings: Settings):
        if not settings.azure_translator_key:
            raise RuntimeError("AZURE_TRANSLATOR_KEY is not set (backend/.env)")
        self._url = settings.azure_translator_endpoint.rstrip("/") + "/translate"
        self._headers = {"Ocp-Apim-Subscription-Key": settings.azure_translator_key, "Content-Type": "application/json"}
        # Required for regional and multi-service resources, harmless for global ones
        if settings.azure_translator_region:
            self._headers["Ocp-Apim-Subscription-Region"] = settings.azure_translator_region
        self._http = httpx.AsyncClient(timeout=settings.azure_translator_timeout_s)

    async def translate_many(self, text: str, source: str, targets: list[str]) -> dict[str, str]:
        params: list[tuple[str, str]] = [("api-version", "3.0")]
        if source:  # empty source -> let Azure auto-detect
            params.append(("from", _azure(source)))
        params += [("to", _azure(t)) for t in targets]

        data = await self._post(params, [{"Text": text}])
        # [{"translations": [{"text": "...", "to": "fr"}, ...]}]
        return {_FROM_AZURE.get(t["to"], t["to"]): t["text"] for t in data[0]["translations"]}

    async def _post(self, params: list[tuple[str, str]], body: list[dict]) -> list[dict]:
        for attempt in range(self.RETRIES + 1):
            last = attempt == self.RETRIES
            try:
                r = await self._http.post(
                    self._url, params=params, json=body,
                    headers={**self._headers, "X-ClientTraceId": str(uuid.uuid4())},
                )
            except httpx.TransportError as e:  # network hiccup / timeout
                if last:
                    raise
                problem = str(e)
            else:
                # Retry only rate limiting (429) and server errors; other 4xx (bad key,
                # unsupported language...) fail immediately
                if r.status_code != 429 and r.status_code < 500:
                    r.raise_for_status()
                    return r.json()
                if last:
                    r.raise_for_status()
                problem = f"HTTP {r.status_code}"
            delay = 0.5 * 2**attempt
            log.warning("Azure Translator attempt %d failed (%s), retrying in %.1fs", attempt + 1, problem, delay)
            await asyncio.sleep(delay)
        raise AssertionError("unreachable")

    async def close(self) -> None:
        await self._http.aclose()


class EchoTranslator(Translator):
    """No-op for development without Azure: returns the text tagged with the target language."""

    name = "echo"

    async def translate_many(self, text: str, source: str, targets: list[str]) -> dict[str, str]:
        return {t: f"[{source}→{t}] {text}" for t in targets}


_BACKENDS: dict[str, type[Translator]] = {"azure": AzureTranslator, "echo": EchoTranslator}


class TranslationService:
    def __init__(self, translator: Translator):
        self.translator = translator

    @property
    def name(self) -> str:
        return self.translator.name

    async def translate_many(self, text: str, source: str, targets: set[str]) -> dict[str, str]:
        """One translation per distinct target language. The source language maps to the text itself."""
        others = sorted(t for t in targets if t != source)
        if not others:
            return {source: text}
        return {source: text, **await self.translator.translate_many(text, source, others)}

    async def close(self) -> None:
        await self.translator.close()


def build_translation_service(settings: Settings) -> TranslationService:
    return TranslationService(_BACKENDS[settings.translator_backend](settings))
