// Convert a recorded audio Blob (webm/opus from MediaRecorder, mp4 on Safari) to a .wav Blob.
// No library needed: the browser decodes the audio, then we write a 16-bit PCM WAV by hand.

/**
 * @param blob        recording from MediaRecorder
 * @param sampleRate  output rate in Hz (16 kHz mono is what speech models expect)
 */
export async function blobToWav(blob: Blob, sampleRate = 16000): Promise<Blob> {
  // 1. Decode the compressed recording into raw samples
  const ctx = new AudioContext()
  const decoded = await ctx.decodeAudioData(await blob.arrayBuffer())
  await ctx.close()

  // 2. Mix down to mono and resample by rendering through an OfflineAudioContext
  const length = Math.ceil(decoded.duration * sampleRate)
  const offline = new OfflineAudioContext(1, length, sampleRate)
  const source = offline.createBufferSource()
  source.buffer = decoded
  source.connect(offline.destination)
  source.start()
  const samples = (await offline.startRendering()).getChannelData(0) // Float32 in [-1, 1]

  return encodeWav(samples, sampleRate)
}

/** Raw mono samples recorded at `srcRate` (e.g. 48 kHz) -> 16 kHz mono .wav Blob. */
export async function samplesToWav(samples: Float32Array<ArrayBuffer>, srcRate: number, sampleRate = 16000): Promise<Blob> {
  const offline = new OfflineAudioContext(1, Math.ceil((samples.length * sampleRate) / srcRate), sampleRate)
  const buffer = offline.createBuffer(1, samples.length, srcRate)
  buffer.copyToChannel(samples, 0)
  const source = offline.createBufferSource()
  source.buffer = buffer
  source.connect(offline.destination)
  source.start()
  return encodeWav((await offline.startRendering()).getChannelData(0), sampleRate)
}

/** Mono Float32 samples -> WAV file (RIFF header + 16-bit little-endian PCM). */
export function encodeWav(samples: Float32Array, sampleRate: number): Blob {
  const bytesPerSample = 2
  const dataSize = samples.length * bytesPerSample
  const view = new DataView(new ArrayBuffer(44 + dataSize))
  const text = (offset: number, s: string) => [...s].forEach((c, i) => view.setUint8(offset + i, c.charCodeAt(0)))

  // 44-byte header
  text(0, 'RIFF')
  view.setUint32(4, 36 + dataSize, true) // file size - 8
  text(8, 'WAVE')
  text(12, 'fmt ')
  view.setUint32(16, 16, true) // fmt chunk size
  view.setUint16(20, 1, true) // format 1 = PCM
  view.setUint16(22, 1, true) // channels: mono
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * bytesPerSample, true) // byte rate
  view.setUint16(32, bytesPerSample, true) // block align
  view.setUint16(34, 16, true) // bits per sample
  text(36, 'data')
  view.setUint32(40, dataSize, true)

  // Samples: clamp to [-1, 1] and scale to 16-bit integers
  let offset = 44
  for (const s of samples) {
    const v = Math.max(-1, Math.min(1, s))
    view.setInt16(offset, v < 0 ? v * 0x8000 : v * 0x7fff, true)
    offset += 2
  }
  return new Blob([view], { type: 'audio/wav' })
}

/** Save a Blob to the user's Downloads folder (e.g. for listening to a recording). */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
