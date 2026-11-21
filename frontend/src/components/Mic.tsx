import { useEffect, useRef, useState } from 'react'

interface MicProps {
  /** Called with the live microphone stream when recording starts. */
  onStart?: (stream: MediaStream) => void
  /** Called when recording stops. */
  onStop?: () => void
}

/**
 * Bottom-of-screen microphone button. Click to start talking to the others,
 * click again to stop. Styles: .mic-bar, .mic-button, .mic-button-active (index.css).
 */
export function Mic({ onStart, onStop }: MicProps) {
  //Returns if recording is true or not (false by default)
  const [recording, setRecording] = useState(false)

  //For error message
  const [error, setError] = useState<string | null>(null)
  
  //Stream reference
  const streamRef = useRef<MediaStream | null>(null)

  //Stop function
  const stop = () => {
    
    //Get the media tracks (radio/video tracks) and stop each of them (includes the mic) to stop stream
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
    setRecording(false)
    onStop?.() //Guarantees error prone
  }

  const start = async () => {
    setError(null)
    //Retrieve mic
    try {
      //Retrieve stream
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
      })
      streamRef.current = stream
      setRecording(true)
      onStart?.(stream)
    } catch {
      setError('Microphone access was denied or is unavailable.')
    }
  }

  // Release the microphone if the component unmounts while recording.
  useEffect(() => () => streamRef.current?.getTracks().forEach((t) => t.stop()), [])

  return (
    <div className="mic-bar flex-col items-center gap-2">
      <button
        type="button"
        className={`mic-button ${recording ? 'mic-button-active' : ''}`}
        onClick={recording ? stop : start}
        aria-pressed={recording}
        aria-label={recording ? 'Stop talking' : 'Start talking'}
        title={recording ? 'Stop talking' : 'Start talking'}
      >
        {recording ? (
          // Stop square
          <svg viewBox="0 0 24 24" className="h-6 w-6" fill="currentColor" aria-hidden="true">
            <rect x="6" y="6" width="12" height="12" rx="2" />
          </svg>
        ) : (
          // Microphone
          <svg
            viewBox="0 0 24 24"
            className="h-7 w-7"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <rect x="9" y="2" width="6" height="12" rx="3" />
            <path d="M5 10v1a7 7 0 0 0 14 0v-1" />
            <line x1="12" y1="18" x2="12" y2="22" />
          </svg>
        )}
      </button>
      <span className="text-xs text-app-muted">
        {error ?? (recording ? 'Listening… click to stop' : 'Click to talk')}
      </span>
    </div>
  )
}
