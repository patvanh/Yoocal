'use client'

interface City {
  key: string
  label: string
}

const CITIES: City[] = [
  { key: 'parkcity', label: '📍 Park City, UT' },
  { key: 'elkhartlake', label: '📍 Elkhart Lake, WI' },
  { key: 'heber', label: '📍 Heber Valley, UT' },
  { key: 'jackson', label: '📍 Jackson Hole, WY' },
]

interface CityChipsBarProps {
  activeCity: string
  onCityChange: (cityKey: string) => void
}

export default function CityChipsBar({ activeCity, onCityChange }: CityChipsBarProps) {
  return (
    <div style={{
      background: 'rgba(83,74,183,0.05)',
      padding: '14px 40px',
      borderTop: '1px solid var(--border)',
      borderBottom: '1px solid var(--border)',
      display: 'flex',
      alignItems: 'center',
      gap: 16,
      flexWrap: 'wrap',
      fontFamily: "'DM Sans', sans-serif",
    }}>
      <span style={{
        fontSize: 12, fontWeight: 700, color: 'var(--muted)',
        textTransform: 'uppercase', letterSpacing: 0.5,
        flexShrink: 0,
      }}>Browse by city</span>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        {CITIES.map(c => {
          const isActive = c.key === activeCity
          return (
            <button
              key={c.key}
              onClick={() => onCityChange(c.key)}
              style={{
                background: isActive ? 'var(--purple)' : 'white',
                color: isActive ? 'white' : 'var(--text)',
                border: '1px solid ' + (isActive ? 'var(--purple)' : 'var(--border)'),
                padding: '7px 16px',
                borderRadius: 100,
                fontSize: 13, fontWeight: 500,
                cursor: 'pointer',
                fontFamily: "'DM Sans', sans-serif",
                whiteSpace: 'nowrap',
                transition: 'all 0.15s',
              }}
            >
              {c.label}
            </button>
          )
        })}
        <a href="#signup" style={{
          background: 'white', color: 'var(--muted)',
          border: '1px solid var(--border)',
          padding: '7px 16px', borderRadius: 100,
          fontSize: 13, fontWeight: 500,
          textDecoration: 'none',
          opacity: 0.5,
        }}>+ Aspen, CO — coming soon</a>
      </div>
    </div>
  )
}
