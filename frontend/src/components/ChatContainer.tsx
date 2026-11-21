import { useRef, useState, type PointerEvent, type ReactNode } from 'react'
import type { SpeakerSlot } from './ChatBubble'

interface ChatContainerProps {
  /** Color slot of the user whose preferred language this container shows (outline color). */
  speaker: SpeakerSlot
  /** Shown on the drag handle, e.g. "Alex · English". */
  label: string
  children: ReactNode // usually <ChatList />
  width?: number
  height?: number
}

/**
 * Round, movable window holding a chat list. Drag it by its top handle
 * anywhere on the screen. Styles: .chat-container / .chat-container-handle (index.css).
 * Future features (e.g. rotation) go here; not implemented yet.
 */
export function ChatContainer({ speaker, label, children, width = 380, height = 480 }: ChatContainerProps) {
  const ref = useRef<HTMLElement>(null)
  
  // Top-left corner in screen pixels; starts centered horizontally under the header
  const [pos, setPos] = useState(() => ({ x: Math.max((window.innerWidth - width) / 2, 8), y: 140 }))
  // Offset between the pointer and the container's corner while dragging
  const drag = useRef<{ dx: number; dy: number } | null>(null)

  const onPointerDown = (e: PointerEvent<HTMLDivElement>) => {
    drag.current = { dx: e.clientX - pos.x, dy: e.clientY - pos.y }
    e.currentTarget.setPointerCapture(e.pointerId) // keep receiving moves even off the handle
  }

  const onPointerMove = (e: PointerEvent<HTMLDivElement>) => {
    const element = ref.current
    if (!drag.current || !element) return
    // Keep the whole container inside the screen
    const maxX = window.innerWidth - element.offsetWidth
    const maxY = window.innerHeight - element.offsetHeight
    setPos({
      x: Math.min(Math.max(e.clientX - drag.current.dx, 0), Math.max(maxX, 0)),
      y: Math.min(Math.max(e.clientY - drag.current.dy, 0), Math.max(maxY, 0)),
    })
  }

  const onPointerUp = () => {
    drag.current = null
  }

  return (
    <section
      ref={ref}
      className={`chat-container speaker-${speaker}`}
      style={{ left: pos.x, top: Math.max(pos.y, 120), width, height }}
      aria-label={`Chat for ${label}`}
    >
      <div
        className="chat-container-handle"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
      >
        {label}
      </div>
      {children}
    </section>
  )
}
