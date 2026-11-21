# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

Babelogue is a CodeJam hackathon project, currently in the planning stage. The repo has only `README`, `Babelogue.png` (the logo) and this file. There is no source code, build system or test suite yet. Add the real commands here once the project is scaffolded.

## What we are building

A real-time conversation translator for **up to 4 people sharing one microphone**. Think of it as "Google Translate for a live group conversation." Each person sees everyone's speech as a live chat, translated into their own preferred language.

### Core user flow

1. **Voice check-in:** each participant registers a short voice sample and a preferred language, and gets their own **color**.
2. **Live speech:** while someone talks, a "live typing" bubble in their color appears in the chat and updates in real time.
3. **Utterance finalized:** when the speaker stops talking (silence detected), the bubble closes and becomes a finalized message.
4. **Language detection + translation:** the spoken language is detected automatically, and the finalized text is translated into each participant's preferred language.
5. **Display:** messages appear on screen as a chat feed with speaker colors.
6. **Text-to-speech on click:** clicking a message plays audio through Azure AI Speech, either the **original speech** (the source text in the source language) or the **speech in the preferred language** (the translation). This is the language-learning feature. Use Azure TTS, **not ElevenLabs**.
7. **Transcript log:** the full conversation history is kept and viewable.
8. **Typing fallback:** a text input box lets users type a message when the mic or venue noise is a problem. It enters the same translate → display → TTS flow.

### Hard requirements

- Ideally **under 5 seconds** from one user speaking to the translated message appearing.
- Supports **up to 4 speakers** on one shared mic.

### Demo "wow" points (in priority order)

1. **Telling apart people who speak the same language.** Speakers are identified by voice, not by language.
2. **Chat history / transcript log.**
3. **Language learning through TTS:** hear both the original and the translation.

## Planned stack

| Layer | Choice | Notes |
|---|---|---|
| Backend | Python + FastAPI | Audio pipeline, ML/API integrations, WebSockets, TTS proxy |
| Frontend | TypeScript + React + Vite + Tailwind CSS | Browser mic capture, WS client, single-screen chat UI (speaker cards, chat feed, audio buttons) |
| Transport | WebSockets + REST | WS streams audio chunks up and live chat events down. REST `/tts` serves audio so Azure keys never reach the browser |
| Voice activity detection | Silero VAD | Detects speech start and pause boundaries. Drives the live bubble and utterance finalization |
| Speaker identification | NVIDIA Streaming Sortformer and/or voice embeddings | Up to 4 speakers. Supported by the voice check-in plus **manual one-tap reassignment** of a bubble to another speaker |
| Speech-to-text + language ID | faster-whisper | Compact, int8-quantized model to stay within the latency budget |
| Translation | TranslateGemma | Translate **finalized** utterances only. Keep a faster fallback ready |
| Text-to-speech | Azure AI Speech | Triggered on click only, proxied through the backend, cached. Watch the Free (F0) tier rate limits |
| Speech separation | Multi-Decoder DPRNN / SepTDA | **Stretch goal only, not in the MVP.** The MVP assumes people take turns speaking |

### Pipeline (backend, per audio stream)

```
mic (browser) ──WS audio chunks──▶ Silero VAD ──speech segment──▶ speaker ID (Sortformer / embeddings)
        ▲                                │ (interim)                         │
        │                                ▼                                   ▼
   chat events ◀──WS── live bubble (partial STT)        finalized utterance ──▶ faster-whisper (text + lang)
                                                                               ──▶ TranslateGemma (per target language)
                                                                               ──▶ final message event to UI
UI click ──REST /tts──▶ Azure TTS (cached) ──▶ audio
```

## Recommendations

- **Define the WebSocket message schema first** (for example `utterance_partial`, `utterance_final`, `speaker_reassign`, `text_message`), with shared types on both sides. The frontend and backend can then be built in parallel against it.
- **Translate once per distinct target language, not once per listener.** If 3 people prefer English, translate to English once.
- **Use the same fixed sample format end to end.** Silero VAD, Sortformer and Whisper all expect 16 kHz mono, so resample in the browser (or once at ingest) before sending chunks.
- **Keep partial and final transcription separate.** For live bubbles, re-run faster-whisper on a rolling buffer, or show a "speaking…" placeholder if that is too slow. Translate only at finalization.
- **Load models once at server startup**, not per request. Sortformer and TranslateGemma are large, so check GPU VRAM early.
- **Cache TTS by (text, language, voice)** so repeated clicks don't use up the F0 quota.
- **Treat the voice check-in and manual reassignment as essential to the demo, not optional extras.** Speaker ID is the riskiest part of the plan.
- **Keep secrets (Azure key/region) in a git-ignored `.env`** that only the backend reads.
