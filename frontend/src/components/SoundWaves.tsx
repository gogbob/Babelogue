import { useEffect, useRef } from 'react'

interface SoundWavesProps {
  /** Live microphone stream (from Mic's onStart). null = flat line. */
  stream: MediaStream | null
  width?: number
  height?: number
}

/**
 * Live waveform of the microphone input, for testing that sound is coming in.
 * Uses the Web Audio API: stream -> AnalyserNode -> canvas, redrawn every frame.
 */
export function SoundWaves({ stream, width = 320, height = 80 }: SoundWavesProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    const ctx = canvas?.getContext('2d')
    if (!canvas || !ctx) return
    const color = getComputedStyle(canvas).color // follows the theme text color

    // Draws one waveform frame (all 128s = silence = flat line)
    const draw = (samples: Uint8Array) => {
      ctx.clearRect(0, 0, width, height)
      ctx.lineWidth = 2
      ctx.strokeStyle = color
      ctx.beginPath()
      samples.forEach((v, i) => {
        const x = (i / (samples.length - 1)) * width
        const y = (v / 255) * height
        if (i === 0) ctx.moveTo(x, y)
        else ctx.lineTo(x, y)
      })
      ctx.stroke()
    }

    //Go to middle
    if (!stream) {
      draw(new Uint8Array(2).fill(128))
      return
    }

    // Connect the mic stream to an analyser (not to the speakers, so no echo)
    const audio = new AudioContext()
    const analyser = audio.createAnalyser()
    analyser.fftSize = 1024
    audio.createMediaStreamSource(stream).connect(analyser)
    const samples = new Uint8Array(analyser.fftSize)

    let frame = 0
    const loop = () => {
      analyser.getByteTimeDomainData(samples) // current waveform, 0-255 centered on 128
      draw(samples)
      frame = requestAnimationFrame(loop)
    }
    loop()

    return () => {
      cancelAnimationFrame(frame)
      audio.close()
    }
  }, [stream, width, height])

  return <canvas ref={canvasRef} width={width} height={height} className="text-app-text" />
}
