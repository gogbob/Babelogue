import { useEffect, useRef, useState } from "react";
import { ChatList, type BubbleMessageProps } from "./components/ChatBubble";
import { ChatContainer } from "./components/ChatContainer";
import { Mic } from "./components/Mic";
import { SoundWaves } from "./components/SoundWaves";
import { ThemeToggle } from "./components/ThemeToggle";
import { SpeakerSlot } from "./components/ChatBubble";
import { AddChatButton } from "./components/AddChatButton";
import { VoiceCalibration, type VoiceSample } from "./components/VoiceCalibration";
import { checkIn, createSession } from "./api/rest";
import { SessionSocket } from "./api/socket";
import type { Participant, ServerMessage, Utterance } from "./api/protocol";

const MAX_PEOPLE = 4;

// One session per page load, shared by the four people on this device.
// Kept outside React so StrictMode's double-run of effects doesn't create two sessions.
let sessionPromise: Promise<string> | null = null;
const getSession = () => (sessionPromise ??= createSession());

/** Add or replace a participant, keeping the list unique by id. */
const upsert = (ps: Participant[], p: Participant) => [...ps.filter((x) => x.id !== p.id), p];

/** One utterance as seen by `reader`: translated into their language, colored by the speaker. */
function toBubble(u: Utterance, reader: Participant, people: Participant[]): BubbleMessageProps {
  const speaker = people.find((p) => p.id === u.participant_id);
  return {
    id: u.id,
    speaker: speaker?.slot ?? null, // null = voice not recognised yet
    text: u.translations[reader.language] ?? u.text, // fall back to the original
    status: u.status,
    time: u.created_at,
  };
}

export default function App() {
  // Live mic stream while recording, null when stopped
  const [stream, setStream] = useState<MediaStream | null>(null);

  // Backend session id (null until created) and any startup error
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessionError, setSessionError] = useState<string | null>(null);
  // People who completed voice calibration; each one gets a chat box in their color slot
  const [participants, setParticipants] = useState<Participant[]>([]);
  // The selected box is on the front layer; all others are on the back layer
  const [selected, setSelected] = useState<SpeakerSlot | null>(null);

  // Voice calibration pop-up, opened by the "+" button
  const [calibrating, setCalibrating] = useState(false);

  // Conversation, in transcript order (live bubbles included)
  const [utterances, setUtterances] = useState<Utterance[]>([]);
  // Last error reported by the backend (GPU, STT or translation)
  const [notice, setNotice] = useState<string | null>(null);
  const socket = useRef<SessionSocket | null>(null);

  useEffect(() => {
    getSession()
      .then(setSessionId)
      .catch((e: Error) => {
        sessionPromise = null; // allow a retry on the next reload
        setSessionError(e.message);
      });
  }, []);

  // WebSocket: mic chunks go up, live/final bubbles come down
  useEffect(() => {
    if (!sessionId) return;
    const put = (u: Utterance) =>
      setUtterances((us) => (us.some((x) => x.id === u.id) ? us.map((x) => (x.id === u.id ? u : x)) : [...us, u]));
    const onMessage = (m: ServerMessage) => {
      switch (m.type) {
        case "session_state":
          setParticipants(m.participants);
          setUtterances(m.utterances);
          break;
        case "participant_joined":
          setParticipants((ps) => upsert(ps, m.participant));
          break;
        case "participant_left":
          setParticipants((ps) => ps.filter((p) => p.id !== m.participant_id));
          break;
        case "utterance_partial":
        case "utterance_final":
        case "utterance_updated":
          put(m.utterance);
          break;
        case "utterance_discarded":
          setUtterances((us) => us.filter((u) => u.id !== m.utterance_id));
          break;
        case "error":
          setNotice(m.message);
          break;
      }
    };
    const s = new SessionSocket(sessionId, onMessage);
    socket.current = s;
    return () => {
      s.close();
      socket.current = null;
    };
  }, [sessionId]);

  // Hide backend errors after a few seconds
  useEffect(() => {
    if (!notice) return;
    const t = setTimeout(() => setNotice(null), 6000);
    return () => clearTimeout(t);
  }, [notice]);

  // Called with the 5-second recording: upload it, and only add the box once the backend saved it.
  // Throwing keeps the pop-up open and shows the error there.
  const addChat = async (sample: VoiceSample) => {
    if (!sessionId) throw new Error("Not connected to the server yet.");
    const person = await checkIn(sessionId, {
      name: `Speaker ${participants.length + 1}`, // names aren't shown in the UI
      language: sample.language,
      audio: sample.audio,
    });
    setParticipants((ps) => upsert(ps, person));
    setSelected(person.slot); // new box starts in front
    setCalibrating(false);
  };

  return (
  <div className="screen-shell">
    <header className="app-header relative flex h-30 items-center justify-center px-4">
      <img src="/BabelogueLogo.png" alt="BabelogueLogo" className="app-logo absolute inset-y-0 left-0 h-full" />
      <h1 className="screen-title">Babelogue</h1>
      <div className="absolute right-4">
        <ThemeToggle />
      </div>
    </header>
    {/* Free space; the chat container floats over the whole screen */}
    <div className="flex-1" />
    {sessionError && (
      <p className="fixed inset-x-0 top-32 z-30 mx-auto w-fit rounded-lg bg-red-100 px-3 py-1 text-sm text-red-700">
        {sessionError} (is the backend running?)
      </p>
    )}
    {notice && !sessionError && (
      <p className="fixed inset-x-0 top-32 z-30 mx-auto w-fit rounded-lg bg-amber-100 px-3 py-1 text-sm text-amber-800">
        {notice}
      </p>
    )}
    {participants.map((person) => (
      <ChatContainer
        key={person.id}
        speaker={person.slot}
        selected={selected === person.slot}
        onSelect={() => setSelected(person.slot)}
      >
        <ChatList messages={utterances.map((u) => toBubble(u, person, participants))} />
      </ChatContainer>
    ))}
    <AddChatButton
      onAdd={() => setCalibrating(true)}
      disabled={!sessionId || participants.length >= MAX_PEOPLE}
    />
    {calibrating && <VoiceCalibration onComplete={addChat} onCancel={() => setCalibrating(false)} />}
    <div className="controls-stack">
      <SoundWaves stream={stream} />
      <Mic
        onStart={setStream}
        // Mic off (after the last chunk was sent): close the open bubbles
        onStop={() => {
          setStream(null);
          socket.current?.sendJson({ type: "flush" });
        }}
        // Each chunk: 5 s of 16 kHz mono .wav, a new one every 3 s, sent over the WebSocket.
        // The backend saves it (voice_samples/<session>/chunks/), then GPU -> Groq -> Azure.
        onChunk={(chunk) => {
          socket.current?.sendChunk(chunk).catch((e: Error) => console.error(e.message));
        }}
      />
    </div>
  </div>
  )
}
