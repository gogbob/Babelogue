// Wire format shared with the backend. Mirror of backend/app/schemas.py: keep both in sync.
//
// WebSocket  /ws/{sessionId}
//   client -> server: binary frames = one 5 s .wav mic chunk each, with a JSON header (see socket.ts)
//                     text frames   = JSON ClientMessage
//   server -> client: text frames   = JSON ServerMessage
//
// REST
//   POST   /api/sessions                                 -> SessionCreated
//   DELETE /api/sessions/{id}
//   POST   /api/sessions/{id}/participants  (multipart: name, language, audio_file ~5 s) -> Participant
//   DELETE /api/sessions/{id}/participants/{participantId}
//   GET    /api/sessions/{id}/transcript                 -> Utterance[]
//   GET    /tts?text=...&language=xx                     -> audio/mpeg

import type { SpeakerSlot } from '../components/ChatBubble'

//The user
export interface Participant {
  id: string
  name: string
  language: string // preferred language, ISO 639-1
  slot: SpeakerSlot // decides the color
}


// Status of a text bubble
export interface Utterance {
  id: string
  participant_id: string | null // null = speaker not recognised yet (reassign it)
  status: 'live' | 'final'
  source: 'voice' | 'text'
  text: string // original text in the source language
  source_language: string | null
  translations: Record<string, string> // target language -> translated text
  start: number | null // seconds since session start (voice only)
  end: number | null
  created_at: number // unix ms
}

export interface SessionCreated {
  session_id: string
}

// ---------- client -> server ----------

export type ClientMessage =
  | { type: 'text_message'; participant_id: string; text: string }
  | { type: 'speaker_reassign'; utterance_id: string; participant_id: string }
  | { type: 'flush' } // mic turned off: close open bubbles now

// ---------- server -> client ----------

export type ServerMessage =
  | { type: 'session_state'; session_id: string; participants: Participant[]; utterances: Utterance[] }
  | { type: 'participant_joined'; participant: Participant }
  | { type: 'participant_left'; participant_id: string }
  | { type: 'utterance_partial'; utterance: Utterance } // live bubble created/updated
  | { type: 'utterance_final'; utterance: Utterance } // bubble closed, translations included
  | { type: 'utterance_updated'; utterance: Utterance } // e.g. reassigned to another speaker
  | { type: 'utterance_discarded'; utterance_id: string } // live bubble was noise: remove it
  | { type: 'error'; message: string }

export const ttsUrl = (text: string, language: string) =>
  `/tts?${new URLSearchParams({ text, language })}`
