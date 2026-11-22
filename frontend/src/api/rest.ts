// REST calls to the FastAPI backend (proxied by Vite: /api -> localhost:8000???).
import type { Participant, SessionCreated } from './protocol'

/** Turn a failed response into a readable message (FastAPI puts it in `detail`). */
async function fail(res: Response, what: string): Promise<never> {
  let detail = `${res.status} ${res.statusText}`
  try {
    const body = await res.json()
    if (typeof body.detail === 'string') detail = body.detail
  } catch {
    /* not JSON */
  }
  throw new Error(`${what}: ${detail}`)
}

/** Create a conversation session. All four people share it on this one device. */
export async function createSession(): Promise<string> {
  const res = await fetch('/api/sessions', { method: 'POST' })
  if (!res.ok) await fail(res, 'Could not start a session')
  return ((await res.json()) as SessionCreated).session_id
}

// File extension matching the recorder's format, so the backend saves e.g. voice.webm
function extensionFor(mime: string): string {
  if (mime.includes('webm')) return 'webm'
  if (mime.includes('ogg')) return 'ogg'
  if (mime.includes('mp4') || mime.includes('aac')) return 'm4a' // Safari / iOS
  if (mime.includes('wav')) return 'wav'
  return 'bin'
}

/**
 * Voice check-in: upload the ~5 s calibration recording + preferred language.
 * The backend saves it, registers the voice with the speaker-ID model, and returns
 * the participant with their color slot (1-4).
 */
export async function checkIn(
  sessionId: string,
  sample: { name: string; language: string; audio: Blob },
): Promise<Participant> {
  const form = new FormData()
  form.append('name', sample.name)
  form.append('language', sample.language)
  form.append('audio_file', sample.audio, `voice.${extensionFor(sample.audio.type)}`)

  const res = await fetch(`/api/sessions/${sessionId}/participants`, { method: 'POST', body: form })
  if (!res.ok) await fail(res, 'Voice calibration failed')
  return res.json()
}

// Mic chunks are sent over the WebSocket, see socket.ts.
