import { useRef, useState } from "react";
import { ChatList } from "./components/ChatBubble";
import { ChatContainer } from "./components/ChatContainer";
import { Mic } from "./components/Mic";
import { SoundWaves } from "./components/SoundWaves";
import { ThemeToggle } from "./components/ThemeToggle";
import { TEST_MESSAGES } from "./testData/chats";
import { SpeakerSlot } from "./components/ChatBubble";
import { AddChatButton } from "./components/AddChatButton";
import { VoiceCalibration, type VoiceSample } from "./components/VoiceCalibration";

// One chat container per person, added in this order (max 4)
const CHATS: SpeakerSlot[] = [1, 2, 3, 4];

export default function App() {
  // Live mic stream while recording, null when stopped
  const [stream, setStream] = useState<MediaStream | null>(null);

  const [chatCount, setChatCount] = useState(0);
  // The selected box is on the front layer; all others are on the back layer
  const [selected, setSelected] = useState<SpeakerSlot | null>(null);

  // Voice calibration pop-up, opened by the "+" button
  const [calibrating, setCalibrating] = useState(false);
  // Each person's voice sample + preferred language, for the recognition AI (backend later)
  const voices = useRef<Partial<Record<SpeakerSlot, VoiceSample>>>({});

  // Called once the person has recorded their 5-second voice sample
  const addChat = (sample: VoiceSample) => {
    if (chatCount >= CHATS.length) return;
    const speaker = CHATS[chatCount];
    voices.current[speaker] = sample;
    setSelected(speaker); // new box starts in front
    setChatCount(chatCount + 1);
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
    {CHATS.slice(0, chatCount).map((speaker) => (
      <ChatContainer
        key={speaker}
        speaker={speaker}
        selected={selected === speaker}
        onSelect={() => setSelected(speaker)}
      >
        <ChatList messages={TEST_MESSAGES} />
      </ChatContainer>
    ))}
    <AddChatButton
      onAdd={() => setCalibrating(true)}
      disabled={chatCount >= CHATS.length}
    />
    {calibrating && <VoiceCalibration onComplete={addChat} onCancel={() => setCalibrating(false)} />}
    <div className="controls-stack">
      <SoundWaves stream={stream} />
      <Mic onStart={setStream} onStop={() => setStream(null)} />
    </div>
  </div>
  )
}
