import { useRef, useState, type PointerEvent, type ReactNode } from 'react'
import type { SpeakerSlot } from './ChatBubble'

interface ChatContainerProps {
  /** Color slot of the user whose preferred language this container shows (outline color). */
  speaker: SpeakerSlot
  children: ReactNode // usually <ChatList />
  width?: number
  height?: number
  /** True for the selected box: it sits on the front layer (--z-chat-front in index.css). */
  selected?: boolean
  /** Called when the box is touched/clicked, so the parent can bring it to the front. */
  onSelect?: () => void
}

/**
 * Round, movable window holding a chat list. Drag it by its top handle
 * anywhere on the screen. Styles: .chat-container / .chat-container-handle (index.css).
 * Future features (e.g. rotation) go here; not implemented yet.
 */
export function ChatContainer({ speaker, children, width = 380, height = 480, selected = false, onSelect }: ChatContainerProps) {
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
    // Keep the whole container inside the screen. Uses the on-screen (rotated)
    // box: `off` is how far the visible box sits from the unrotated corner.
    const box = element.getBoundingClientRect()
    const offX = box.left - pos.x
    const offY = box.top - pos.y
    const clamp = (v: number, min: number, max: number) => Math.min(Math.max(v, min), Math.max(max, min))
    setPos({
      x: clamp(e.clientX - drag.current.dx, -offX, window.innerWidth - box.width - offX),
      y: clamp(e.clientY - drag.current.dy, -offY, window.innerHeight - box.height - offY),
    })
  }

  // Rotation in degrees. Keeps growing (90, 180, 270, 360…) so the
  // animation always turns clockwise instead of snapping back from 270 to 0.
  const [rotation, setRotation] = useState(0)

  const onPointerUp = () => {
    drag.current = null
  }

  return (
    <section
      ref={ref}
      className={`chat-container speaker-${speaker} ${selected ? 'chat-container-front' : ''}`}
      // Rotating the whole section turns everything inside, including the bubbles
      style={{ left: pos.x, top: Math.max(pos.y, 120), width, height, transform: `rotate(${rotation}deg)` }}
      // Capture phase: runs before the drag/scroll handlers and never blocks them,
      // so scrolling the bubbles still works on the selected box
      onPointerDownCapture={onSelect}
      aria-label="Chat box"
    >
      <div
        className="chat-container-handle"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
      >
        {/* Mobile only (hidden on PC by CSS): rotate the box 90° clockwise */}
        <button
          type="button"
          className="rotate-button"
          onPointerDown={(e) => e.stopPropagation()} // tapping it must not start a drag
          onClick={() => setRotation((r) => r + 90)}
          aria-label="Rotate chat 90 degrees"
          title="Rotate chat 90°"
        >
          <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M21 12a9 9 0 1 1-2.64-6.36" />
            <path d="M21 3v6h-6" />
          </svg>
        </button>
      </div>
      {children}
    </section>
  )
}
