# Babelogue

**Contributors:** Christophe Lewis, Thomas Alexandrescu, Tony Yang

**GitHub:** https://github.com/gogbob/Babelogue

## 1. Project Overview

Babelogue is a real-time multilingual conversation application designed to allow up to **4 participants** to communicate in different languages.

Each participant speaks their native language, and the application automatically transcribes and translates their speech into the preferred language of every other participant.

**Main objectives:**
- Target under 5 seconds from the end of an utterance to translated text delivery.
- Support up to 4 concurrent speakers.
- Identify participants using voice embeddings established during an initial calibration phase.
- Display translated messages with unique speaker IDs and colors.
- Support live audio streaming using WebSockets.
- Provide text input as a fallback when speech recognition is unreliable.

## 2. Current Infrastructure

Babelogue's React frontend has already been deployed publicly.

**Hosting:**
- Proxmox home server running a dedicated Ubuntu VM named `public1`.
- Isolated network: `pubnet` (`10.20.30.0/24`).
- VM IP: `10.20.30.10`.
- Docker Engine and Docker Compose installed.
- GitHub repository cloned into `/opt/public-apps/hackathon/Babelogue`.
- Frontend built with Docker and served through Nginx.
- Cloudflare Tunnel named `public1-babelogue` is connected and healthy.
- Public website accessible over HTTPS through Cloudflare.

The public VM is isolated from the server's private infrastructure. No inbound router port forwarding is required, and the private home-server services remain inaccessible externally.

**Technology stack:**

| Layer | Technology |
|---|---|
| Frontend | React, TypeScript, Vite, Tailwind CSS |
| Backend | Python, FastAPI |
| Real-time communication | WebSockets + REST |
| Containerization | Docker Compose |
| Public access | Cloudflare Tunnel |
| Private GPU connectivity | Tailscale |
| Speech recognition | Whisper via Groq / FreeLLMAPI |
| Speaker recognition | GPU-based embeddings and diarization |
| Translation | Gemini API |
| Text-to-speech | Azure AI TTS, optional/on click |

## 3. Proposed Architecture

```text
                  PUBLIC USERS
             (up to 4 participants)
                       |
                HTTPS / WSS
                       |
               Cloudflare Tunnel
                       |
                public1 (Docker)
                       |
              React + Nginx
                       |
               FastAPI Backend
              (Main Orchestrator)
                       |
          +------------+------------+
          |            |            |
      GPU Node      STT API      Gemini API
      Tailscale     Whisper      Translation
          |            |            |
     Speaker ID     Speech to    Per-language
     Embeddings       Text        translations
     Diarization
          |
     Audio source
      separation
     (stretch goal)
```

**Important:** The public FastAPI backend will coordinate operations, but heavy GPU inference will happen on a teammate's separate machine.

Only the frontend and necessary API/WebSocket routes will be accessible publicly. The GPU node will remain private.

## 4. Speech Processing Pipeline

### Phase A — Participant registration and calibration

When a participant joins:

1. Frontend assigns a temporary participant/session ID.
2. Participant records approximately 5 seconds of speech.
3. Frontend uploads audio to FastAPI.
4. FastAPI forwards calibration audio to the private GPU node.
5. GPU generates a voice embedding for that participant.
6. Backend stores or references the embedding using the participant ID.
7. Speech recognition detects the participant's spoken language.
8. Frontend assigns a unique color and confirms the participant's preferred translation language.

**Result:** Each participant has a speaker ID, voice profile, display color, and language preference.

Voice embeddings are intended to improve speaker recognition, but they are not guaranteed to identify speakers perfectly. The frontend should support manual one-tap speaker reassignment.

### Phase B — Real-time speech processing

```text
Microphone
    ↓
Audio chunks over WebSocket
    ↓
FastAPI receives and buffers audio
    ↓
Silero VAD detects speech boundaries
    ↓
Speaker identification
    ↓
Whisper STT
    ↓
Gemini translation
    ↓
FastAPI broadcasts translated events
    ↓
Frontend displays speaker-colored messages
```

**Backend endpoints:**

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Check backend status |
| `POST /api/sessions` | Create conversation |
| `POST /api/sessions/{id}/join` | Register participant |
| `POST /api/speakers/calibrate` | Submit voice calibration |
| `WS /ws/sessions/{id}` | Stream audio and receive live events |
| `POST /api/transcribe` | Speech-to-text testing |
| `POST /api/translate` | Translation testing |

Testing endpoints should be authenticated or disabled in the public production configuration.

## 6. Speech-to-Text Decision

- Groq-hosted Whisper: fast hosted inference, no local GPU requirement.
- FreeLLMAPI: routing layer that can use different supported providers and their quotas.

**Reasoning:** The remote GPU is primarily intended for speaker identification and separation. Offloading transcription to an API reduces competition for GPU resources.

## 7. Translation Architecture

Gemini will translate finalized utterances into every unique target language requested by participants.

For example:

- Participant A speaks English.
- Participant B speaks French.
- Participant C speaks Spanish.
- Participant D speaks Mandarin.

When Participant B speaks French, the backend produces English, Spanish, and Mandarin translations.

Rather than calling Gemini separately for every participant, the backend can request translations for all unique target languages in a single structured response.
