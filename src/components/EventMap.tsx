// No 'use client' needed - this is a pure HTML iframe, works on server

interface EventMapProps {
  lat: number
  lng: number
  title: string
  location: string
}

export default function EventMap({ lat, lng, title, location }: EventMapProps) {
  const delta = 0.006
  const bbox = `${lng - delta},${lat - delta},${lng + delta},${lat + delta}`
  const embedUrl = `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&layer=mapnik&marker=${lat},${lng}`
  const fullUrl = `https://www.openstreetmap.org/?mlat=${lat}&mlon=${lng}#map=15/${lat}/${lng}`

  return (
    <div style={{ marginBottom: 40 }}>
      <h2 style={{
        fontFamily: "'DM Serif Display', serif",
        fontSize: 22,
        color: 'var(--dark)',
        marginBottom: 16,
      }}>
        Location
      </h2>
      <div style={{ borderRadius: 16, overflow: 'hidden', border: '1px solid var(--border)' }}>
        <iframe
          title={`Map: ${title} at ${location}`}
          src={embedUrl}
          width="100%"
          height="280"
          style={{ display: 'block', border: 'none' }}
          loading="lazy"
          referrerPolicy="no-referrer-when-downgrade"
        />
      </div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 10 }}>
        <p style={{ fontSize: 13, color: 'var(--muted)' }}>📍 {location}</p>
        <a href={fullUrl} target="_blank" rel="noopener noreferrer"
          style={{ fontSize: 12, color: 'var(--purple)', textDecoration: 'none' }}>
          Open in maps →
        </a>
      </div>
    </div>
  )
}
