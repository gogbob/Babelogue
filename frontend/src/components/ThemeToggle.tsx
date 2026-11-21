import { useEffect, useState } from 'react'

const STORAGE_KEY = 'babelogue-theme'

// Start from the saved choice, else the OS preference.
function initialDark(): boolean {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) return saved === 'dark'
  } catch {
    /* storage blocked: fall through */
  }
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

/**
 * Light/dark mode switch. Adds/removes the `dark` class on <html>, which
 * swaps every color token in index.css (background, bubbles, text, mic, waves).
 * Light mode shows a black moon (go dark); dark mode shows a white sun (go light).
 */
export function ThemeToggle() {
  const [dark, setDark] = useState(initialDark)

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
    try {
      localStorage.setItem(STORAGE_KEY, dark ? 'dark' : 'light')
    } catch {
      /* storage blocked: theme just won't be remembered */
    }
  }, [dark])

  const label = dark ? 'Switch to light mode' : 'Switch to dark mode'

  return (
    <button type="button" className="icon-button" onClick={() => setDark((d) => !d)} aria-label={label} title={label}>
      {dark ? (
        // White sun
        <svg viewBox="0 0 24 24" className="h-6 w-6" fill="#ffffff" stroke="#ffffff" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
          <circle cx="12" cy="12" r="4" />
          <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
        </svg>
      ) : (
        // Black moon
        <svg viewBox="0 0 24 24" className="h-6 w-6" fill="#000000" aria-hidden="true">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
        </svg>
      )}
    </button>
  )
}
