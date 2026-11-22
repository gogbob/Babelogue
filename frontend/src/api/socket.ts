// WebSocket client for /ws/{sessionId}. Sends mic chunks up and receives chat events down.
// Binary chunk layout (must match backend/app/coordinator.py):
//   [4 bytes header length N, uint32 little-endian][N bytes JSON {index,start,end}][.wav file]
import type { AudioChunk } from '../audio/chunkRecorder'
import type { ClientMessage, ServerMessage } from './protocol'

const RETRY_MS = 1500

export class SessionSocket {
  private ws: WebSocket | null = null
  private pending: (ArrayBuffer | string)[] = [] // sent once the socket is open
  private closed = false

  constructor(
    private sessionId: string,
    private onMessage: (msg: ServerMessage) => void,
  ) {
    this.connect()
  }

  /** One 5 s .wav chunk from the mic. */
  async sendChunk(chunk: AudioChunk): Promise<void> {
    const header = new TextEncoder().encode(
      JSON.stringify({ index: chunk.index, start: chunk.start, end: chunk.end }),
    )
    const wav = new Uint8Array(await chunk.wav.arrayBuffer())
    const out = new Uint8Array(4 + header.length + wav.length)
    new DataView(out.buffer).setUint32(0, header.length, true)
    out.set(header, 4)
    out.set(wav, 4 + header.length)
    this.send(out.buffer)
  }

  /** JSON message, e.g. { type: 'flush' } when the mic turns off. */
  sendJson(msg: ClientMessage): void {
    this.send(JSON.stringify(msg))
  }

  close(): void {
    this.closed = true
    this.ws?.close()
  }

  private send(data: ArrayBuffer | string) {
    if (this.ws?.readyState === WebSocket.OPEN) this.ws.send(data)
    else this.pending.push(data)
  }

  private connect() {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    const ws = new WebSocket(`${proto}://${location.host}/ws/${this.sessionId}`)
    ws.binaryType = 'arraybuffer'
    ws.onopen = () => {
      for (const data of this.pending.splice(0)) ws.send(data)
    }
    ws.onmessage = (e) => {
      if (typeof e.data === 'string') this.onMessage(JSON.parse(e.data) as ServerMessage)
    }
    ws.onclose = () => {
      if (!this.closed) setTimeout(() => this.connect(), RETRY_MS) // backend restarted / network blip
    }
    this.ws = ws
  }
}
