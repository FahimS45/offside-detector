// src/pages/Home.tsx
import { useRef, useState } from 'react'
import UploadBox       from '../components/UploadBox'
import ProcessingState from '../components/ProcessingState'
import VerdictCard     from '../components/VerdictCard'
import VideoPlayer     from '../components/VideoPlayer'
import { uploadVideo, openAnalysisSocket, videoUrl, type WSEvent } from '../api/client'

type Stage = 'idle' | 'uploading' | 'scanning' | 'picking' | 'processing' | 'done' | 'error'

interface Result { verdict: string; confidence: number; videoSrc?: string }

export default function Home() {
  const [stage,     setStage]     = useState<Stage>('idle')
  const [status,    setStatus]    = useState('')
  const [colours,   setColours]   = useState<{ team_a_hex: string; team_b_hex: string } | null>(null)
  const [progress,  setProgress]  = useState<{ frame: number; total: number } | null>(null)
  const [result,    setResult]    = useState<Result | null>(null)
  const [error,     setError]     = useState('')
  const [direction, setDirection] = useState<'left' | 'right'>('left')  // lifted here — survives re-renders

  const sessionRef  = useRef<string>('')
  const sendTeamRef = useRef<((t: 'team_a' | 'team_b') => void) | null>(null)

  const handleUpload = async (file: File, dir: 'left' | 'right') => {
    setStage('uploading')
    setStatus('Uploading…')
    try {
      const { session_id } = await uploadVideo(file, dir)
      sessionRef.current   = session_id
      setStage('scanning')
      setStatus('Connecting…')

      const { sendTeamSelect, close } = openAnalysisSocket(session_id, (evt: WSEvent) => {
        switch (evt.type) {
          case 'status':
            setStatus(evt.message)
            break

          case 'colour_options':
            setColours({ team_a_hex: evt.team_a_hex, team_b_hex: evt.team_b_hex })
            setStage('picking')
            setStatus('Pick the attacking team jersey colour')
            break

          case 'progress':
            setStage('processing')
            setStatus('Analysing frames…')
            setProgress({ frame: evt.frame, total: evt.total })
            break

          case 'complete':
            setResult({
              verdict:    evt.verdict,
              confidence: evt.confidence,
              videoSrc:   evt.video_url ?? videoUrl(session_id),
            })
            setStage('done')
            close()
            break

          case 'error':
            setError(evt.message)
            setStage('error')
            close()
            break
        }
      })

      sendTeamRef.current = sendTeamSelect
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Upload failed')
      setStage('error')
    }
  }

  const handleTeamPick = (team: 'team_a' | 'team_b') => {
    sendTeamRef.current?.(team)
    setColours(null)
    setStage('processing')
    setStatus('Processing video…')
  }

  const reset = () => {
    setStage('idle'); setStatus(''); setColours(null)
    setProgress(null); setResult(null); setError('')
    // direction intentionally kept so user doesn't have to re-select
  }

  return (
    <main style={styles.main}>
      <header style={styles.header}>
        <h1 style={styles.title}>OFFSIDE<span style={{ color: 'var(--accent)' }}>AI</span></h1>
        <p style={styles.sub}>Offside detection · YOLOv8 + ByteTrack</p>
      </header>

      <div style={styles.content}>
        {(stage === 'idle' || stage === 'uploading') && (
          <UploadBox
            onUpload={handleUpload}
            loading={stage === 'uploading'}
            direction={direction}
            onDirection={setDirection}
          />
        )}

        {(stage === 'scanning' || stage === 'picking' || stage === 'processing') && (
          <ProcessingState
            status={status}
            colours={stage === 'picking' ? colours : null}
            progress={stage === 'processing' ? progress : null}
            onTeamPick={handleTeamPick}
          />
        )}

        {stage === 'done' && result && (
          <>
            <VerdictCard verdict={result.verdict} confidence={result.confidence} onReset={reset} />
            {result.videoSrc && <VideoPlayer src={result.videoSrc} />}
          </>
        )}

        {stage === 'error' && (
          <div style={styles.errBox}>
            <p style={{ color: 'var(--accent2)', fontFamily: 'var(--font-mono)', fontSize: '0.9rem' }}>{error}</p>
            <button onClick={reset} style={styles.errBtn}>TRY AGAIN</button>
          </div>
        )}
      </div>
    </main>
  )
}

const styles: Record<string, React.CSSProperties> = {
  main:    { minHeight: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '3rem 1.5rem' },
  header:  { textAlign: 'center', marginBottom: '2.5rem' },
  title:   { fontSize: 'clamp(2.5rem, 6vw, 4rem)', fontWeight: 700, letterSpacing: '0.06em', lineHeight: 1 },
  sub:     { fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: 'var(--muted)', marginTop: '0.4rem' },
  content: { display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1.5rem', width: '100%' },
  errBox:  { display: 'flex', flexDirection: 'column', gap: '1rem', alignItems: 'flex-start', maxWidth: 480, width: '100%', background: 'var(--surface)', border: '1px solid var(--accent2)', borderRadius: 8, padding: '1.2rem' },
  errBtn:  { padding: '0.5rem 1.2rem', background: 'var(--accent2)', color: '#fff', borderRadius: 4, fontWeight: 700, fontSize: '0.85rem', cursor: 'pointer' },
}