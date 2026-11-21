import { useState } from "react";
import { Mic } from "./components/Mic";
import { SoundWaves } from "./components/SoundWaves";

export default function App() {
  // Live mic stream while recording, null when stopped
  const [stream, setStream] = useState<MediaStream | null>(null);

  return (
    <div className="flex h-screen flex-col items-center justify-center gap-4 bg-slate-50">
      <h1 className="text-3xl font-bold text-slate-800">Babelogue</h1>
      <SoundWaves stream={stream} />
      <Mic onStart={setStream} onStop={() => setStream(null)} />
    </div>
  )
}
