import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Offline — Yoocal',
  robots: { index: false, follow: false },
}

export default function OfflinePage() {
  return (
    <div style={{
      minHeight: '100vh', display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center', textAlign: 'center',
      background: '#1a1830', color: '#fff', fontFamily: "'DM Sans', sans-serif", padding: 24,
    }}>
      <div style={{ width: 64, height: 64, borderRadius: '50%', background: '#534AB7', marginBottom: 24 }} />
      <h1 style={{ fontFamily: "'DM Serif Display', serif", fontSize: 32, margin: '0 0 10px' }}>You&apos;re offline</h1>
      <p style={{ color: 'rgba(255,255,255,0.6)', fontSize: 16, maxWidth: 360, lineHeight: 1.5 }}>
        Yoocal needs a connection to load the latest events. Reconnect and try again.
      </p>
    </div>
  )
}
