import { slotFor, type BubbleMessageProps } from '../components/ChatBubble'

// Test cases: 4 people, each with their own list of chats.
// `at` = seconds into the conversation, used to interleave everyone's chats.
// Alex and Sam both speak English (same-language speakers must still get different colors).
interface TestChat {
  at: number
  text: string
  status?: 'live' | 'final' // default 'final'
}

interface TestPerson {
  name: string
  chats: TestChat[]
}

export const TEST_PEOPLE: TestPerson[] = [
  {
    name: 'Alex', // 1st → red
    chats: [
      { at: 0, text: 'Hey everyone, thanks for joining the call.' },
      { at: 40, text: 'Great, let me share my screen.' },
      { at: 90, text: 'Any questions before we wrap up?' },
    ],
  },
  {
    name: 'Sam', // 2nd → blue
    chats: [
      { at: 10, text: 'Same here. Should we start with the demo plan?' },
      { at: 60, text: 'This is a longer message to check that the bubble wraps nicely when someone talks for a while without stopping, which happens a lot in real conversations.' },
      { at: 100, text: 'Not from me.\nThanks all!' }, // multi-line
    ],
  },
  {
    name: 'Camille', // 3rd → yellow
    chats: [
      { at: 20, text: "Bonjour ! Je suis ravie d'être ici." },
      { at: 70, text: "C'est très clair, merci." },
    ],
  },
  {
    name: 'Lucía', // 4th → green
    chats: [
      { at: 30, text: 'Sí, primero mostramos el historial del chat.' },
      { at: 80, text: '¡Perfecto!' }, // very short
      { at: 110, text: 'Una pregunta rápida sobre', status: 'live' }, // still talking
    ],
  },
]

const PEOPLE = TEST_PEOPLE.map((p) => p.name)
const START = Date.now() - 2 * 60 * 1000 // conversation started 2 minutes ago

/** All test chats flattened into one list, in conversation order. */
export const TEST_MESSAGES: BubbleMessageProps[] = TEST_PEOPLE.flatMap((person) =>
  person.chats.map((chat, i) => ({
    id: `${person.name}-${i}`,
    name: person.name,
    speaker: slotFor(person.name, PEOPLE),
    text: chat.text,
    status: chat.status ?? 'final',
    time: START + chat.at * 1000,
  })),
).sort((a, b) => a.time - b.time)

console.log(TEST_MESSAGES)
