// src/components/VerdictCard.tsx
interface Props {
  verdict:    string
  confidence: number
  onReset:    () => void
}

export default function VerdictCard({ verdict, confidence, onReset }: Props) {
  const isOffside = verdict.toLowerCase().includes('offside')
  const accent    = isOffside ? 'var(--accent2)' : 'var(--accent)'

  return (
    <div style={{ ...styles.card, borderColor: accent }}>
      <p style={styles.label}>VERDICT</p>
      <p style={{ ...styles.verdict, color: accent }}>{verdict.toUpperCase()}</p>
      <p style={styles.conf}>Confidence: <strong>{(confidence * 100).toFixed(1)}%</strong></p>
      <button onClick={onReset} style={styles.reset}>ANALYSE ANOTHER CLIP</button>
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  card:    { border: '1px solid', borderRadius: 8, padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '0.6rem', background: 'var(--surface)', maxWidth: 480, width: '100%' },
  label:   { fontFamily: 'var(--font-mono)', fontSize: '0.72rem', letterSpacing: '0.12em', color: 'var(--muted)' },
  verdict: { fontSize: '2.2rem', fontWeight: 700, letterSpacing: '0.04em' },
  conf:    { fontFamily: 'var(--font-mono)', fontSize: '0.85rem', color: 'var(--muted)' },
  reset:   { marginTop: '0.5rem', padding: '0.55rem', background: 'transparent', border: '1px solid var(--border)', borderRadius: 4, color: 'var(--text)', fontWeight: 600, fontSize: '0.85rem', letterSpacing: '0.08em', cursor: 'pointer' },
}
