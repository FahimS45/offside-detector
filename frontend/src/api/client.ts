// src/api/client.ts
// Handles HTTP upload + WebSocket pipeline

export type WSEvent =
  | { type: 'status';         message: string }
  | { type: 'colour_options'; team_a_hex: string; team_b_hex: string; referee_hex?: string }
  | { type: 'progress';       frame: number; total: number; verdict: string; confidence: number }
  | { type: 'complete';       verdict: string; confidence: number; video_url?: string }
  | { type: 'error';          message: string }

const BASE = import.meta.env.VITE_API_BASE ?? ''

// Helper to construct accurate target URLs for the videos
export function videoUrl(sessionId: string): string {
  // If BASE is relative or empty, default to current origin, otherwise point to backend target
  const origin = BASE ? new URL(BASE).origin : window.location.origin;
  return `${origin}/video/${sessionId}`;
}

// Helper utility to safely trigger binary cross-origin file downloads 
async function triggerAutoDownload(url: string, sessionId: string) {
  try {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`Video fetch failed: ${response.statusText}`);
    
    const blob = await response.blob();
    const blobUrl = window.URL.createObjectURL(blob);
    
    const tempLink = document.createElement('a');
    tempLink.href = blobUrl;
    tempLink.download = `offside_analysis_${sessionId}.mp4`;
    
    document.body.appendChild(tempLink);
    tempLink.click();
    
    // Clean memory footprint
    document.body.removeChild(tempLink);
    window.URL.revokeObjectURL(blobUrl);
    console.log('[Download] Auto download complete for session:', sessionId);
  } catch (err) {
    console.error('[Download] Auto download failed:', err);
  }
}

// ── Step 0: upload file via HTTP ──────────────────────────────────────────────
export async function uploadVideo(
  file: File,
  direction: 'left' | 'right',
): Promise<{ session_id: string; direction: string }> {
  const form = new FormData()
  form.append('file', file)
  form.append('direction', direction)

  const res = await fetch(`${BASE}/upload`, { method: 'POST', body: form })
  if (!res.ok) throw new Error(`Upload failed: ${res.statusText}`)
  return res.json()
}

// ── Steps 1-3: WebSocket pipeline ─────────────────────────────────────────────
export function openAnalysisSocket(
  sessionId: string,
  onEvent: (e: WSEvent) => void,
): {
  sendTeamSelect: (team: 'team_a' | 'team_b') => void
  close: () => void
} {
  const proto  = location.protocol === 'https:' ? 'wss' : 'ws'
  const host   = BASE ? new URL(BASE).host : location.host
  const ws     = new WebSocket(`${proto}://${host}/ws/analyse/${sessionId}`)

  ws.onopen    = () => console.log('[WS] connected')
  
  ws.onmessage = (e) => { 
    try { 
      const rawData = JSON.parse(e.data) as WSEvent;
      
      // Intercept the processing completion event to trigger auto-download
      if (rawData.type === 'complete') {
        const targetUrl = rawData.video_url || videoUrl(sessionId);
        triggerAutoDownload(targetUrl, sessionId);
      }
      
      onEvent(rawData);
    } catch (err) { 
      console.error('[WS] Parse error', err);
    } 
  }
  
  ws.onerror   = (e) => { console.error('[WS] error', e); onEvent({ type: 'error', message: 'WebSocket error' }) }
  ws.onclose   = () => console.log('[WS] closed')

  const sendTeamSelect = (team: 'team_a' | 'team_b') => {
    ws.send(JSON.stringify({ type: 'team_select', attacking_team: team }))
  }

  return { sendTeamSelect, close: () => ws.close() }
}