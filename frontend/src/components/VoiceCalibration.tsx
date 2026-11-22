import { useEffect, useRef, useState } from 'react'
import { SoundWaves } from './SoundWaves'
import { blobToWav } from '../audio/wav'

const RECORD_SECONDS = 10

// Languages the person can pick as their preferred language
export const LANGUAGES = [
  { code: 'en', name: 'English' },
  { code: 'fr', name: 'Français' },
  { code: 'es', name: 'Español' },
  { code: 'de', name: 'Deutsch' },
  { code: 'zh', name: '中文' },
  { code: 'ja', name: '日本語' },
  { code: 'ar', name: 'العربية' },
  { code: 'pt', name: 'Português' },
]

export interface VoiceSample {
  audio: Blob // 5-second recording as a 16 kHz mono .wav, uploaded to the backend
  language: string // preferred language code, e.g. 'fr'
}

interface VoiceCalibrationProps {
  /** Uploads the sample; the pop-up shows "Saving…" until it resolves and shows the error if it throws. */
  onComplete: (sample: VoiceSample) => Promise<void>
  onCancel: () => void
}

type Step = 'idle' | 'recording' | 'done' | 'saving'

/**
 * Pop-up shown by the "+" button. The new person records 5 seconds of their
 * voice in their preferred language so the AI can recognize them later.
 * Styles: .modal-backdrop, .modal (index.css); mic reuses .mic-button.
 */
export function VoiceCalibration({ onComplete, onCancel }: VoiceCalibrationProps) {
  const [step, setStep] = useState<Step>('idle')
  const [language, setLanguage] = useState('en')
  const [secondsLeft, setSecondsLeft] = useState(RECORD_SECONDS)
  const [stream, setStream] = useState<MediaStream | null>(null)
  const [error, setError] = useState<string | null>(null)
  const audio = useRef<Blob | null>(null)
  const timer = useRef<number | undefined>(undefined)
  const micRef = useRef<MediaStream | null>(null)

  // Release the mic and stop the countdown
  const releaseMic = () => {
    clearInterval(timer.current)
    micRef.current?.getTracks().forEach((t) => t.stop())
    micRef.current = null
    setStream(null)
  }
  // Also release if the pop-up closes mid-recording
  useEffect(() => releaseMic, [])

  // Escape closes the pop-up (except mid-recording)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && step !== 'recording' && step !== 'saving' && onCancel()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [step, onCancel])

  const record = async () => {
    setError(null)
    let mic: MediaStream
    try {
      mic = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } })
    } catch {
      setError('Microphone access was denied or is unavailable.')
      return
    }
    const chunks: Blob[] = []
    const recorder = new MediaRecorder(mic)
    recorder.ondataavailable = (e) => chunks.push(e.data)
    recorder.onstop = async () => {
      releaseMic()
      const recorded = new Blob(chunks, { type: recorder.mimeType })
      try {
        audio.current = await blobToWav(recorded) // 16 kHz mono .wav
      } catch {
        audio.current = recorded // browser couldn't decode it: upload the original instead
      }
      setStep('done')
    }

    micRef.current = mic
    setStream(mic)
    setStep('recording')
    setSecondsLeft(RECORD_SECONDS)
    recorder.start()

    // Count down each second, stop at 0. A short extra tail keeps the clip safely
    // above the backend's 4.5 s minimum (it trims to exactly 5 s).
    let left = RECORD_SECONDS
    timer.current = window.setInterval(() => {
      left -= 1
      setSecondsLeft(left)
      if (left <= 0) {
        clearInterval(timer.current)
        window.setTimeout(() => recorder.stop(), 300)
      }
    }, 1000)
  }

  // Send the recording to the backend; stay open with the error if it fails
  const save = async () => {
    if (!audio.current) return
    setStep('saving')
    setError(null)
    try {
      await onComplete({ audio: audio.current, language })
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Saving the voice sample failed.')
      setStep('done')
    }
  }

  const recording = step === 'recording'
  const busy = recording || step === 'saving'

  return (
    <div className="modal-backdrop" onClick={() => !busy && onCancel()}>
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby="calib-title" onClick={(e) => e.stopPropagation()}>
        <h2 id="calib-title" className="text-lg font-bold">Voice calibration</h2>
        <p className="text-sm text-app-muted">
          Choose your preferred language, press the mic and speak for {RECORD_SECONDS} seconds so Babelogue can recognize your voice.
        </p>

        <select
          className="modal-select"
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
          disabled={busy}
          aria-label="Preferred language"
        >
          {LANGUAGES.map((language) => (
            <option key={language.code} value={language.code}>{language.name}</option>
          ))}
        </select>

        <button
          type="button"
          className={`mic-button ${recording ? 'mic-button-active' : ''}`}
          onClick={record}
          disabled={busy}
          aria-label={step === 'done' ? 'Record again' : 'Start recording'}
        >
          {recording ? (
            <span className="text-xl font-bold">{secondsLeft}</span>
          ) : (
            <svg viewBox="0 0 24 24" className="h-7 w-7" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <rect x="9" y="2" width="6" height="12" rx="3" />
              <path d="M5 10v1a7 7 0 0 0 14 0v-1" />
              <line x1="12" y1="18" x2="12" y2="22" />
            </svg>
          )}
        </button>
        <SoundWaves stream={stream} width={240} height={48} />

        <p className="min-h-5 text-sm" aria-live="polite">
          {error ?? (recording ? `Recording… ${secondsLeft}s left` : step === 'saving' ? 'Saving your voice…' : step === 'done' ? '✓ Voice recorded. Press the mic to redo it.' : 'Press the mic to start')}
        </p>

        <div className="flex w-full justify-end gap-2">
          <button type="button" className="modal-button" onClick={onCancel} disabled={busy}>
            Cancel
          </button>
          <button
            type="button"
            className="modal-button modal-button-primary"
            disabled={step !== 'done'}
            onClick={save}
          >
            {step === 'saving' ? 'Saving…' : 'Add chat'}
          </button>
        </div>
      </div>
    </div>
  )
}
