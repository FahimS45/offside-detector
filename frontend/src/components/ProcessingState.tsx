// src/components/ProcessingState.tsx
interface Props {
  status:     string
  colours:    { team_a_hex: string; team_b_hex: string } | null
  progress:   { frame: number; total: number } | null
  onTeamPick: (team: 'team_a' | 'team_b') => void
}

export default function ProcessingState({ status, colours, progress, onTeamPick }: Props) {
  const pct = progress ? Math.round((progress.frame / progress.total) * 100) : 0

  return (
    <div style={styles.wrap}>
      <p style={styles.status}>{status}</p>

      {colours && (
        <div style={styles.section}>
          <p style={styles.label}>SELECT ATTACKING TEAM JERSEY</p>
          <div style={styles.swatches}>
            {(['team_a', 'team_b'] as const).map((t) => (
              <button key={t} onClick={() => onTeamPick(t)} style={styles.swatch}>
                <span style={{ ...styles.dot, background: t === 'team_a' ? colours.team_a_hex : colours.team_b_hex }} />
                <span>{t === 'team_a' ? colours.team_a_hex.toUpperCase() : colours.team_b_hex.toUpperCase()}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {progress && (
        <div style={styles.section}>
          <div style={styles.barTrack}>
            <div style={{ ...styles.barFill, width: `${pct}%` }} />
          </div>
          <p style={styles.mono}>{progress.frame} / {progress.total} frames · {pct}%</p>
        </div>
      )}
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  wrap:    { display: 'flex', flexDirection: 'column', gap: '1.2rem', width: '100%', maxWidth: 480 },
  status:  { fontFamily: 'var(--font-mono)', fontSize: '0.85rem', color: 'var(--accent)', minHeight: 20 },
  section: { display: 'flex', flexDirection: 'column', gap: '0.6rem' },
  label:   { fontSize: '0.72rem', letterSpacing: '0.1em', color: 'var(--muted)', fontFamily: 'var(--font-mono)' },
  swatches:{ display: 'flex', gap: 12 },
  swatch:  { flex: 1, display: 'flex', alignItems: 'center', gap: 10, padding: '0.7rem 1rem', background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text)', fontWeight: 600, fontSize: '0.9rem', fontFamily: 'var(--font-mono)', cursor: 'pointer', transition: 'border-color .15s' },
  dot:     { width: 22, height: 22, borderRadius: '50%', flexShrink: 0, border: '2px solid rgba(255,255,255,.15)' },
  barTrack:{ height: 6, background: 'var(--border)', borderRadius: 3, overflow: 'hidden' },
  barFill: { height: '100%', background: 'var(--accent)', borderRadius: 3, transition: 'width .3s ease' },
  mono:    { fontFamily: 'var(--font-mono)', fontSize: '0.78rem', color: 'var(--muted)' },
}
