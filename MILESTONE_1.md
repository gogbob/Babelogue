# Babelogue milestone 1: staged Docker deployment

Scope: deploy current upstream FastAPI code with mock GPU, dummy STT, echo translation. Existing public frontend stays untouched.

Verified source paths: `backend/app/main.py` (`/health`), `backend/mock_audio_service/main.py` (`/health`), backend settings read env from `backend/.env`, API paths `/api/sessions`, `/ws/{session_id}`, `/tts`.

## Prerequisites

Run commands on `public1` after connecting via SSH. Repository path: `/opt/public-apps/hackathon/Babelogue` (check actual path before using). Confirm the existing Compose filename and network before installing:

```
cd /opt/public-apps/hackathon/Babelogue
pwd
ls -la
sudo docker compose config --services
sudo docker compose config --networks
```

This kit assumes root Compose file is `compose.yaml`, with services `frontend`, `cloudflared` and network `app_net`. If yours differs, adjust paths/names in `compose.backend.yaml` before proceeding.

## Secret env file

Your teammate's private file belongs in `backend/.env`, NOT in the repository root `.env` that holds the Cloudflare Tunnel token. Keep them separate. Do not overwrite a working root `.env`, and never commit or send keys in chat. The `.dockerignore` prevents sending the backend `.env` into the Docker build context. The repo root `.gitignore` already excludes `.env`.

After securely copying the env file (or copying `.env.example` and populating it locally):

```
chmod 600 backend/.env
```

M1's Compose overlay explicitly overrides STT_BACKEND=dummy, TRANSLATOR_BACKEND=echo, AUDIO_SERVICE_URL=http://mock-audio:8001, PARTIAL_TRANSCRIPTS=false so real API credentials are not needed yet. The existing Azure credentials in your private env file are still passed to the backend but should not be exposed in logs/screenshots.

## Install kit files

Copy `backend/Dockerfile`, `backend/.dockerignore`, `compose.backend.yaml`, and `nginx/gateway.conf` into their matching paths under your Babelogue checkout. Back up or compare any existing file before overwriting. `gateway.conf` is intended for the separate gateway container, not the existing frontend Nginx image.

## Validate, build, test

```
cd /opt/public-apps/hackathon/Babelogue
sudo docker compose -f compose.yaml -f compose.backend.yaml config --quiet
sudo docker compose -f compose.yaml -f compose.backend.yaml up -d --build backend mock-audio gateway
sudo docker compose -f compose.yaml -f compose.backend.yaml ps
sudo docker compose -f compose.yaml -f compose.backend.yaml logs --tail=70 backend mock-audio gateway
```

Check FastAPI in-container:

```
sudo docker compose -f compose.yaml -f compose.backend.yaml exec backend python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health').read().decode())"
```

Check reverse-proxy routing from the staging gateway:

```
sudo docker compose -f compose.yaml -f compose.backend.yaml exec gateway wget -qO- http://127.0.0.1/api/health
sudo docker compose -f compose.yaml -f compose.backend.yaml exec gateway wget -qO- http://127.0.0.1/ | head -c 300
```

`/api/health` is a gateway alias for the existing backend `/health`. Health can report an audio-service status of ready. If the service is unhealthy, inspect logs and verify service-name DNS resolution.

## IMPORTANT: public exposure is a separate controlled step

Cloudflare Tunnel should REMAIN routed to `http://frontend:80` at the end of milestone 1. Do not switch to `http://gateway:80` until session auth, quotas/rate limits and an appropriate Access policy have been implemented. The existing REST session, WebSocket, and Azure TTS endpoints are not suitable for unrestricted public access. If you choose a closed team-only demo, Cloudflare Access can guard the new gateway hostname/route, but make sure it does not unintentionally block browser WebSockets.

When it is safe to cut over, change the existing published Cloudflare hostname's service URL from `http://frontend:80` to `http://gateway:80`. Rollback: switch back to `http://frontend:80`. Never expose port 8000 through Docker `ports:` or router forwarding.

## Next milestones

1. Introduce authentication / per-session authorization and API/TTS quotas; validate the frontend's actual WS event schema against `backend/app/schemas.py`.
2. Enable Azure Translator (and TTS) using existing settings; use unique target languages and test credentials independently.
3. Add GroqTranscriber as a third provider to `backend/app/services/transcriber.py`; set STT_BACKEND=groq, PARTIAL_TRANSCRIPTS=false; handle 429 and bound queues. Groq's 25 MB free limit is *per uploaded file*; RPM, RPD, ASH, ASD also apply.
4. Add private Tailscale reachability and use real GPU API endpoints documented in `API_PCGPU.md`. Keep only one worker while sessions are in RAM.
5. Load/stress test: 4 speakers, transcription and translation latency, session clean-up, abuse protection, reconnect handling.
