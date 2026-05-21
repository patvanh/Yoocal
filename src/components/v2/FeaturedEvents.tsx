'use client'

import { ReactNode } from 'react'

interface FeaturedEventsProps {
  children: ReactNode  // Pass EventCards as children
  count?: number
}

export default function FeaturedEvents({ children, count }: FeaturedEventsProps) {
  return (
    <section style={{
      background: 'linear-gradient(135deg, #FAEEDA 0%, #FCD9A8 50%, #FAEEDA 100%)',
      padding: '32px 0',
      borderTop: '1px solid rgba(239,159,39,0.2)',
      borderBottom: '1px solid rgba(239,159,39,0.2)',
      fontFamily: "'DM Sans', sans-serif",
    }}>
      <div style={{
        maxWidth: 880,
        margin: '0 auto',
        padding: '0 16px',
      }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 12,
          marginBottom: 16,
        }}>
          <div style={{
            display: 'inline-flex', alignItems: 'center', gap: 6,
            background: 'var(--amber)', color: 'white',
            padding: '4px 14px', borderRadius: 100,
            fontSize: 12, fontWeight: 700,
            textTransform: 'uppercase', letterSpacing: 0.5,
          }}>
            ★ Featured
          </div>
          {count != null && (
            <span style={{ fontSize: 13, color: 'rgba(154,52,18,0.7)', fontWeight: 500 }}>
              {count} this {count === 1 ? 'event' : 'events'} hand-picked
            </span>
          )}
        </div>
        {children}
      </div>
    </section>
  )
}
