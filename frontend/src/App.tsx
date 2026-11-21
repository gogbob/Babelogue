import { useState } from "react";
import { ChatList } from "./components/ChatBubble";
import { ChatContainer } from "./components/ChatContainer";
import { Mic } from "./components/Mic";
import { SoundWaves } from "./components/SoundWaves";
import { ThemeToggle } from "./components/ThemeToggle";
import { TEST_MESSAGES } from "./testData/chats";

export default function App() {
  // Live mic stream while recording, null when stopped
  const [stream, setStream] = useState<MediaStream | null>(null);

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
    <ChatContainer speaker={1} label="Alex · English">
      <ChatList messages={TEST_MESSAGES} />
    </ChatContainer>
    <ChatContainer speaker={2} label="Sam · English">
      <ChatList messages={TEST_MESSAGES} />
    </ChatContainer>
    <ChatContainer speaker={3} label="Lucia · English">
      <ChatList messages={TEST_MESSAGES} />
    </ChatContainer>
    <ChatContainer speaker={4} label="Camille · English">
      <ChatList messages={TEST_MESSAGES} />
    </ChatContainer>
    
    <div className="controls-stack">
      <SoundWaves stream={stream} />
      <Mic onStart={setStream} onStop={() => setStream(null)} />
    </div>
  </div>
  )
}
