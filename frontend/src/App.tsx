import { useState } from "react";
import { ChatList } from "./components/ChatBubble";
import { Mic } from "./components/Mic";
import { SoundWaves } from "./components/SoundWaves";
import { ThemeToggle } from "./components/ThemeToggle";
import { TEST_MESSAGES } from "./testData/chats";

export default function App() {
  // Live mic stream while recording, null when stopped
  const [stream, setStream] = useState<MediaStream | null>(null);

  return (
  <div className="screen-shell">
    <header className="app-header relative justify-center">
      <h1 className="screen-title">Babelogue</h1>
      <div className="absolute right-4">
        <ThemeToggle />
      </div>
    </header>
    <ChatList messages={TEST_MESSAGES} />
    <div className="controls-stack">
      <SoundWaves stream={stream} />
      <Mic onStart={setStream} onStop={() => setStream(null)} />
    </div>
  </div>
  )
}
