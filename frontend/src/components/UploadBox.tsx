// src/components/UploadBox.tsx
import { useRef, useState } from 'react'

interface Props {
  onUpload:    (file: File, direction: 'left' | 'right') => void
  loading:     boolean
  direction:   'left' | 'right'
  onDirection: (d: 'left' | 'right') => void
}

export default function UploadBox({ onUpload, loading, direction, onDirection }: Props) {
  const inputRef            = useRef<HTMLInputElement>(null)
  const [drag, setDrag]     = useState(false)
  const [chosen, setChosen] = useState<File | null>(null)

  const submit = () => {
    if (chosen) onUpload(chosen, direction)
  }

  return (
    <div style={styles.wrap}>
      <div
        style={{ ...styles.dropzone, borderColor: drag ? 'var(--accent)' : 'var(--border)' }}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDrag(true) }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); const f = e.dataTransfer.files[0]; if (f) setChosen(f) }}
      >
        <input ref={inputRef} type="file" accept="video/*" onChange={(e) => { const f = e.target.files?.[0]; if (f) setChosen(f) }} />
        <span style={styles.icon}>▶</span>
        <p style={styles.label}>{chosen ? chosen.name : 'Drop clip or click to select'}</p>
        <p style={styles.hint}>10–15 sec video · MP4 preferred</p>
      </div>

      <div style={styles.row}>
        <label style={styles.fieldLabel}>ATTACKING DIRECTION</label>
        <div style={styles.toggle}>
          {(['left', 'right'] as const).map((d) => (
            <button
              key={d}
              onClick={() => onDirection(d)}
              style={{ ...styles.toggleBtn, ...(direction === d ? styles.toggleActive : {}) }}
            >
              {d === 'left' ? '← LEFT' : 'RIGHT →'}
            </button>
          ))}
        </div>
      </div>

      <button onClick={submit} disabled={!chosen || loading} style={{ ...styles.btn, opacity: (!chosen || loading) ? 0.4 : 1 }}>
        {loading ? 'UPLOADING…' : 'ANALYSE'}
      </button>
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  wrap:        { display: 'flex', flexDirection: 'column', gap: '1.2rem', width: '100%', maxWidth: 480 },
  dropzone:    { border: '1px dashed', borderRadius: 8, padding: '2.5rem 1.5rem', textAlign: 'center', cursor: 'pointer', transition: 'border-color .2s', background: 'var(--surface)' },
  icon:        { fontSize: '2rem', display: 'block', marginBottom: '0.5rem', color: 'var(--accent)' },
  label:       { fontSize: '1rem', fontWeight: 600, marginBottom: 4 },
  hint:        { fontSize: '0.8rem', color: 'var(--muted)', fontFamily: 'var(--font-mono)' },
  row:         { display: 'flex', flexDirection: 'column', gap: '0.4rem' },
  fieldLabel:  { fontSize: '0.75rem', letterSpacing: '0.12em', color: 'var(--muted)', fontFamily: 'var(--font-mono)' },
  toggle:      { display: 'flex', gap: 8 },
  toggleBtn:   { flex: 1, padding: '0.5rem', background: 'var(--surface)', color: 'var(--muted)', border: '1px solid var(--border)', borderRadius: 4, fontWeight: 700, fontSize: '0.85rem', transition: 'all .15s' },
  toggleActive:{ background: 'var(--accent)', color: '#000', borderColor: 'var(--accent)' },
  btn:         { padding: '0.75rem', background: 'var(--accent)', color: '#000', borderRadius: 4, fontWeight: 700, fontSize: '1rem', letterSpacing: '0.1em', transition: 'opacity .15s' },
}