// Records the live microphone continuously and cuts it into overlapping .wav chunks:
// a 5 s window every 3 s (3 s hop), i.e. 0-5 s, 3-8 s, 6-11 s, ...
// Timing is counted in audio samples (not timers), so chunks are exactly aligned.
import { samplesToWav } from './wav'

export interface AudioChunk {
  wav: Blob // 16 kHz mono .wav
  index: number // 0, 1, 2, ...
  start: number // seconds since the mic was turned on
  end: number
}

// Tiny AudioWorklet that hands every block of mic samples to the main thread.
// Inlined as a Blob URL so it needs no separate file.
const TAP_WORKLET = `
class Tap extends AudioWorkletProcessor {
  process(inputs) {
    const channel = inputs[0][0]
    if (channel) this.port.postMessage(channel.slice(0))
    return true
  }
}
registerProcessor('chunk-tap', Tap)
`

export class ChunkRecorder {
  private ctx: AudioContext | null = null
  private frames: Float32Array[] = [] // only the most recent `window` seconds are kept
  private buffered = 0 // samples currently in `frames`
  private total = 0 // samples received since start
  private lastEnd = 0 // sample position where the last emitted chunk ended
  private nextEmit = 0 // sample position at which the next chunk is due
  private index = 0
  private rate = 48000
  private encoding: Promise<void> = Promise.resolve() // keeps chunks in order

  constructor(
    private onChunk: (chunk: AudioChunk) => void,
    private windowSec = 5,
    private hopSec = 3,
  ) {}

  async start(stream: MediaStream): Promise<void> {
    this.ctx = new AudioContext()
    this.rate = this.ctx.sampleRate
    this.nextEmit = this.windowSec * this.rate // first chunk once 5 s are recorded

    const url = URL.createObjectURL(new Blob([TAP_WORKLET], { type: 'text/javascript' }))
    await this.ctx.audioWorklet.addModule(url)
    URL.revokeObjectURL(url)

    const source = this.ctx.createMediaStreamSource(stream)
    const tap = new AudioWorkletNode(this.ctx, 'chunk-tap')
    tap.port.onmessage = (e: MessageEvent<Float32Array>) => this.push(e.data)
    // Route through a muted gain to the output so the browser keeps pulling audio
    // through the tap, without playing the mic back on the speakers.
    const mute = this.ctx.createGain()
    mute.gain.value = 0
    source.connect(tap).connect(mute).connect(this.ctx.destination)
  }

  /** Stop recording. Audio after the last chunk is sent as one final (≤ 5 s) chunk. */
  async stop(): Promise<void> {
    if (this.total > this.lastEnd) this.emit(Math.min(this.total, this.windowSec * this.rate))
    await this.ctx?.close()
    this.ctx = null
    await this.encoding
  }

  private push(frame: Float32Array) {
    this.frames.push(frame)
    this.buffered += frame.length
    this.total += frame.length

    // Forget audio older than one window
    const keep = this.windowSec * this.rate
    while (this.buffered - this.frames[0].length >= keep) this.buffered -= this.frames.shift()!.length

    if (this.total >= this.nextEmit) {
      this.emit(keep)
      this.nextEmit += this.hopSec * this.rate // next one 3 s later
    }
  }

  /** Cut the last `length` samples and encode them to .wav (in order, off the audio path). */
  private emit(length: number) {
    const all = new Float32Array(this.buffered)
    let offset = 0
    for (const f of this.frames) {
      all.set(f, offset)
      offset += f.length
    }
    const samples = all.slice(-length)
    const end = this.total
    const meta = { index: this.index++, start: (end - samples.length) / this.rate, end: end / this.rate }
    this.lastEnd = end

    this.encoding = this.encoding.then(async () => {
      this.onChunk({ wav: await samplesToWav(samples, this.rate), ...meta })
    })
  }
}
