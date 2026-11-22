import { useEffect, useState } from "react";
import { ChatList } from "./components/ChatBubble";
import { ChatContainer } from "./components/ChatContainer";
import { Mic } from "./components/Mic";
import { SoundWaves } from "./components/SoundWaves";
import { ThemeToggle } from "./components/ThemeToggle";
import { TEST_MESSAGES } from "./testData/chats";
import { SpeakerSlot } from "./components/ChatBubble";
import { AddChatButton } from "./components/AddChatButton";
import { VoiceCalibration, type VoiceSample } from "./components/VoiceCalibration";
import { checkIn, createSession, uploadChunk } from "./api/rest";
import type { Participant } from "./api/protocol";

const MAX_PEOPLE = 4;

// One session per page load, shared by the four people on this device.
// Kept outside React so StrictMode's double-run of effects doesn't create two sessions.
let sessionPromise: Promise<string> | null = null;
const getSession = () => (sessionPromise ??= createSession());

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

  useEffect(() => {
    getSession()
      .then(setSessionId)
      .catch((e: Error) => {
        sessionPromise = null; // allow a retry on the next reload
        setSessionError(e.message);
      });
  }, []);

  // Called with the 5-second recording: upload it, and only add the box once the backend saved it.
  // Throwing keeps the pop-up open and shows the error there.
  const addChat = async (sample: VoiceSample) => {
    if (!sessionId) throw new Error("Not connected to the server yet.");
    const person = await checkIn(sessionId, {
      name: `Speaker ${participants.length + 1}`, // names aren't shown in the UI
      language: sample.language,
      audio: sample.audio,
    });
    setParticipants((ps) => [...ps, person]);
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
    {participants.map((person) => (
      <ChatContainer
        key={person.id}
        speaker={person.slot}
        selected={selected === person.slot}
        onSelect={() => setSelected(person.slot)}
      >
        <ChatList messages={TEST_MESSAGES} />
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
        onStop={() => setStream(null)}
        // Each chunk: 5 s of 16 kHz mono .wav, a new one every 3 s. Saved by the backend in
        // voice_samples/<session id>/chunks/
        onChunk={(chunk) => {
          if (!sessionId) return;
          uploadChunk(sessionId, chunk).catch((e: Error) => console.error(e.message));
        }}
      />
    </div>
  </div>
  )
}
