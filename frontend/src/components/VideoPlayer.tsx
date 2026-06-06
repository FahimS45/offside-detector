// src/components/VideoPlayer.tsx
interface Props { src: string }

export default function VideoPlayer({ src }: Props) {
  return (
    <div style={styles.wrap}>
      <p style={styles.label}>ANNOTATED OUTPUT</p>
      <video
        key={src}
        controls
        autoPlay
        loop
        playsInline
        style={styles.video}
      >
        <source src={src} type="video/mp4" />
        Your browser does not support the video tag.
      </video>
      <a href={src} download style={styles.download}>⬇ Download annotated video</a>
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  wrap:     { display: 'flex', flexDirection: 'column', gap: '0.5rem', width: '100%', maxWidth: 760 },
  label:    { fontFamily: 'var(--font-mono)', fontSize: '0.72rem', letterSpacing: '0.12em', color: 'var(--muted)' },
  video:    { width: '100%', borderRadius: 8, border: '1px solid var(--border)', background: '#000' },
  download: { fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: 'var(--accent)', textDecoration: 'none', alignSelf: 'flex-start' },
}