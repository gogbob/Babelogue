import { useEffect, useRef } from 'react'

/** Speaker slot 1-4 → red, blue, yellow, green (colors live in index.css). */
export type SpeakerSlot = 1 | 2 | 3 | 4

export interface BubbleMessageProps {
  id: string
  speaker: SpeakerSlot | null // which person said it; decides the bubble color (null = not recognised)
  text: string
  status: 'live' | 'final' // live = still talking, final = stopped talking
  time?: number // ms timestamp, shown once the message is final
}

/**
 * One chat bubble. Styles from index.css:
 * - .bubble + .speaker-N  → color set for person N
 * - .bubble-live          → update state (faded, dashed edge, blinking cursor)
 * - .bubble-final         → end state (solid)
 */
export function ChatBubble({ message: m }: { message: BubbleMessageProps }) {
  //Is bubble still not done
  const live = m.status === 'live'
  
  // Time format
  const time = m.time
    ? new Date(m.time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : ''

  return (
    <div className={`flex items-start gap-2 speaker-${m.speaker ?? 'unknown'}`}>
      {/* Colored dot so the person is recognizable even at a glance */}
      <span
        className="mt-2 h-3 w-3 shrink-0 rounded-full"
        style={{ background: 'var(--bubble-accent)' }}
      />
      <div className={`bubble ${live ? 'bubble-live' : 'bubble-final'}`} aria-live={live ? 'polite' : 'off'}>
        <span className="text-xs opacity-60">{live ? 'speaking…' : time}</span>
        <p className="bubble-text mt-0.5 whitespace-pre-wrap break-words">{m.text}</p>
      </div>
    </div>
  )
}

//Creates the message list
/** Scrolling list of bubbles; keeps the newest message in view. */
export function ChatList({ messages }: { messages: BubbleMessageProps[] }) {
  const end = useRef<HTMLDivElement>(null)

  //Whenever messages changes, scroll into the view the current message
  // Braces matter: newer browsers return a Promise from scrollIntoView,
  // and React treats any returned value as a cleanup function.
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto p-4">
      {messages.map((m) => (
        <ChatBubble key={m.id} message={m} />
      ))}
      <div ref={end} />
    </div>
  )
}

/**
 * Color slot for a person from their position in the participant list
 * (1st person = red, 2nd = blue, 3rd = yellow, 4th = green).
 */
//Attributing slot out of 4 ppl
export function slotFor(personId: string, people: string[]): SpeakerSlot {
  return ((Math.max(people.indexOf(personId), 0) % 4) + 1) as SpeakerSlot
}
