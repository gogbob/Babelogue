interface AddChatButtonProps {
  onAdd: () => void
  disabled: boolean // true once the max number of chat containers is reached
}

/**
 * Round "+" button in the middle of the screen that adds a chat container.
 * Follows light/dark theme; grays out when disabled. Styles: .add-chat-button (index.css).
 */
export function AddChatButton({ onAdd, disabled }: AddChatButtonProps) {
  const label = disabled ? 'Maximum number of chats reached' : 'Add a chat'

  return (
    <button type="button" className="add-chat-button" onClick={onAdd} disabled={disabled} aria-label={label} title={label}>
      <svg viewBox="0 0 24 24" className="h-8 w-8" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden="true">
        <path d="M12 5v14M5 12h14" />
      </svg>
    </button>
  )
}
