'use client'

import { useEffect, useRef } from 'react'

interface EventMapProps {
  lat: number
  lng: number
  title: string
  location: string
}

export default function EventMap({ lat, lng, title, location }: EventMapProps) {
  const mapRef = useRef<HTMLDivElement>(null)
  const mapInitialized = useRef(false)

  useEffect(() => {
    if (!mapRef.current || mapInitialized.current) return

    // Wait for Leaflet to be available
    const init = () => {
      const L = (window as any).L
      if (!L) { setTimeout(init, 200); return }

      mapInitialized.current = true
      const map = L.map(mapRef.current!, {
        center: [lat, lng],
        zoom: 15,
        zoomControl: true,
        scrollWheelZoom: false,
        dragging: true,
      })

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
      }).addTo(map)

      const icon = L.divIcon({
        html: `<div style="background:var(--purple,#534AB7);width:14px;height:14px;border-radius:50%;border:3px solid white;box-shadow:0 2px 8px rgba(0,0,0,0.3)"></div>`,
        className: '',
        iconSize: [14, 14],
        iconAnchor: [7, 7],
      })

      L.marker([lat, lng], { icon })
        .addTo(map)
        .bindPopup(`<strong>${title}</strong><br/>${location}`)
        .openPopup()
    }

    init()
  }, [lat, lng, title, location])

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
      <div
        ref={mapRef}
        style={{
          height: 280,
          borderRadius: 16,
          overflow: 'hidden',
          border: '1px solid var(--border)',
        }}
      />
      <p style={{ fontSize: 13, color: 'var(--muted)', marginTop: 10 }}>
        📍 {location}
      </p>
    </div>
  )
}
