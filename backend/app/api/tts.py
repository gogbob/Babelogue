"""REST /tts: Azure speech for a message, proxied so the Azure key never reaches the browser.

GET works directly as an <audio src>:  /tts?text=Bonjour&language=fr
"""

from fastapi import APIRouter, HTTPException, Query, Request, Response

from ..schemas import TTSRequest
from ..services.tts import MEDIA_TYPE, TTSError

router = APIRouter(tags=["tts"])


async def _speak(request: Request, text: str, language: str) -> Response:
    try:
        audio = await request.app.state.services.tts.synthesize(text, language)
    except TTSError as e:
        raise HTTPException(503, str(e))
    return Response(audio, media_type=MEDIA_TYPE, headers={"Cache-Control": "public, max-age=86400"})


@router.get("/tts")
async def tts_get(request: Request, text: str = Query(min_length=1, max_length=1000), language: str = Query()):
    return await _speak(request, text, language)


@router.post("/tts")
async def tts_post(request: Request, body: TTSRequest):
    return await _speak(request, body.text, body.language)
