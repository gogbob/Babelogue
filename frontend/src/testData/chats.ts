import type { BubbleMessageProps, SpeakerSlot } from '../components/ChatBubble'

// Test cases: 4 people (speaker slots 1-4), each with their own list of chats.
// `at` = seconds into the conversation, used to interleave everyone's chats.
// Speakers 1 and 2 both speak English (same-language speakers must still get different colors).
interface TestChat {
  at: number
  text: string
  status?: 'live' | 'final' // default 'final'
}

interface TestPerson {
  speaker: SpeakerSlot // 1 = red, 2 = blue, 3 = yellow, 4 = green
  chats: TestChat[]
}

export const TEST_PEOPLE: TestPerson[] = [
  {
    speaker: 1,
    chats: [
      { at: 0, text: 'Hey everyone, thanks for joining the call.' },
      { at: 40, text: 'Great, let me share my screen.' },
      { at: 90, text: 'Any questions before we wrap up?' },
    ],
  },
  {
    speaker: 2,
    chats: [
      { at: 10, text: 'Same here. Should we start with the demo plan?' },
      { at: 60, text: 'This is a longer message to check that the bubble wraps nicely when someone talks for a while without stopping, which happens a lot in real conversations.' },
      { at: 100, text: 'Not from me.\nThanks all!' }, // multi-line
    ],
  },
  {
    speaker: 3,
    chats: [
      { at: 20, text: "Bonjour ! Je suis ravie d'être ici." },
      { at: 70, text: "C'est très clair, merci." },
    ],
  },
  {
    speaker: 4,
    chats: [
      { at: 30, text: 'Sí, primero mostramos el historial del chat.' },
      { at: 80, text: '¡Perfecto!' }, // very short
      { at: 110, text: 'Una pregunta rápida sobre', status: 'live' }, // still talking
    ],
  },
]

const START = Date.now() - 2 * 60 * 1000 // conversation started 2 minutes ago

/** All test chats flattened into one list, in conversation order. */
export const TEST_MESSAGES: BubbleMessageProps[] = TEST_PEOPLE.flatMap((person) =>
  person.chats.map((chat, i) => ({
    id: `${person.speaker}-${i}`,
    speaker: person.speaker,
    text: chat.text,
    status: chat.status ?? 'final',
    time: START + chat.at * 1000,
  })),
).sort((a, b) => a.time - b.time)

console.log(TEST_MESSAGES)
