"""Babelogue main backend. Run from backend/:  uvicorn app.main:app --port 8000"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .api import sessions, tts, ws
from .config import get_settings
from .services.audio_service import AudioServiceClient
from .services.transcriber import build_transcriber
from .services.translator import build_translation_service
from .services.tts import AzureTTS
from .session import Services, SessionManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("babelogue")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    # Models load once here, not per request.
    services = Services(
        settings=settings,
        audio=AudioServiceClient(settings.audio_service_url, settings.sample_rate, settings.audio_service_timeout_s),
        transcriber=build_transcriber(settings),
        translator=build_translation_service(settings),
        tts=AzureTTS(settings),
    )
    app.state.services = services
    app.state.sessions = SessionManager(services)
    log.info("ready (audio service: %s)", settings.audio_service_url)
    yield
    await app.state.sessions.close_all()
    await services.audio.close()
    await services.translator.close()
    await services.tts.close()


app = FastAPI(title="Babelogue", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_origins,
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(sessions.router)
app.include_router(tts.router)
app.include_router(ws.router)


@app.get("/health")
async def health(request: Request):
    services = request.app.state.services
    try:
        audio = await services.audio.health()
    except Exception as e:
        audio = {"status": "unreachable", "error": str(e)}
    return {
        "status": "ok",
        "audio_service": audio,
        "stt": services.settings.stt_backend,
        "translator": services.translator.name,
        "active_sessions": len(request.app.state.sessions.sessions),
    }
