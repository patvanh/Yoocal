'use client'

interface HeroSectionProps {
  cityName: string
  todayLabel: string  // e.g. "WED, May 20"
  eventCountThisWeek?: number
}

export default function HeroSection({ cityName, todayLabel, eventCountThisWeek }: HeroSectionProps) {
  return (
    <section style={{
      background: 'linear-gradient(135deg, #1a1830 0%, #2a1d4f 50%, #1a1830 100%)',
      color: 'white',
      padding: '80px 40px 60px',
      textAlign: 'center',
      position: 'relative',
      overflow: 'hidden',
      fontFamily: "'DM Sans', sans-serif",
    }}>
      <div style={{ maxWidth: 880, margin: '0 auto' }}>
        <div style={{
          fontSize: 13, color: 'var(--purple-mid)',
          textTransform: 'uppercase', letterSpacing: 1,
          marginBottom: 14,
        }}>Live calendar</div>
        <h1 style={{
          fontFamily: "'DM Serif Display', serif",
          fontSize: 'clamp(40px, 6vw, 64px)',
          fontWeight: 400,
          lineHeight: 1.05,
          margin: '0 0 16px',
        }}>
          What's happening <em style={{ color: 'var(--purple-light)' }}>now</em>
        </h1>
        <div style={{
          fontSize: 16, color: 'rgba(255,255,255,0.7)',
          marginBottom: 8,
        }}>
          {todayLabel} — {cityName}
        </div>
        {eventCountThisWeek != null && (
          <div style={{ fontSize: 14, color: 'rgba(255,255,255,0.5)', marginTop: 8 }}>
            {eventCountThisWeek} events this week
          </div>
        )}
      </div>
    </section>
  )
}
