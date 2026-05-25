'use client'

import { ReactNode } from 'react'

interface PageShellProps {
  children: ReactNode
  cityKey?: 'parkcity' | 'heber' | 'jackson' | 'elkhartlake'
}

export default function PageShell({ children, cityKey = 'parkcity' }: PageShellProps) {
  const aboutHref = {
    parkcity: '/about/park-city',
    heber: '/about/heber',
    elkhartlake: '/about/elkhart-lake',
    jackson: '/about/jackson-hole',
  }[cityKey] || '/about'
  
  const aboutLabel = {
    parkcity: 'About Park City',
    heber: 'About Heber Valley',
    elkhartlake: 'About Elkhart Lake',
    jackson: 'About Jackson Hole',
  }[cityKey] || 'About'
  
  return (
    <>
      {/* NAV */}
      <nav style={{
        position: 'fixed', top: 0, left: 0, right: 0, zIndex: 100,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 40px', height: 64,
        background: 'rgba(250,249,255,0.85)',
        backdropFilter: 'blur(8px)',
        borderBottom: '1px solid var(--border)',
        fontFamily: "'DM Sans', sans-serif",
      }}>
        <a href="/" style={{
          display: 'flex', alignItems: 'center', gap: 8,
          color: 'var(--purple)', fontWeight: 700, fontSize: 22,
          textDecoration: 'none', fontFamily: "'DM Sans', sans-serif",
        }}>
          <div style={{
            width: 8, height: 8, borderRadius: '50%',
            background: 'var(--amber)',
          }} />
          yoocal
        </a>
        <div style={{ display: 'flex', alignItems: 'center', gap: 32 }}>
          <a href={aboutHref} style={navLink}>{aboutLabel}</a>
          <a href="/this-weekend" style={navLink}>This Weekend</a>
          <a href="/venues" style={navLink}>Venues</a>
          <a href="/submit" style={navLinkOutline}>Submit event</a>
          <a href="#business" style={navLink}>For businesses</a>
          <a href="https://forms.groupmail.info/subscribe/yoocal" target="_blank" rel="noopener noreferrer" style={navCta}>
            Get notified
          </a>
        </div>
      </nav>
      
      {/* MAIN CONTENT */}
      <div style={{
        paddingTop: 64,
        minHeight: '100vh',
        background: 'var(--bg)',
        fontFamily: "'DM Sans', sans-serif",
        color: 'var(--text)',
      }}>
        {children}
      </div>
      
      {/* FOOTER */}
      <footer style={{
        background: '#1a1830',
        color: 'rgba(255,255,255,0.7)',
        padding: '60px 80px 24px',
        fontFamily: "'DM Sans', sans-serif",
      }}>
        <div style={{
          display: 'flex', justifyContent: 'space-between',
          maxWidth: 1100, margin: '0 auto', marginBottom: 40,
          flexWrap: 'wrap', gap: 40,
        }}>
          <div>
            <a href="/" style={{
              display: 'flex', alignItems: 'center', gap: 8,
              color: 'white', fontWeight: 700, fontSize: 22,
              textDecoration: 'none', marginBottom: 8,
            }}>
              <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--amber)' }} />
              yoocal
            </a>
            <div style={{ fontSize: 14, color: 'rgba(255,255,255,0.4)' }}>Your local, everywhere.</div>
          </div>
          <div style={{ display: 'flex', gap: 60 }}>
            <FooterCol title="Product" links={[
              ['Browse events', '#events'],
              ['How it works', '#how'],
              ['Newsletter', '#signup'],
            ]} />
            <FooterCol title="Business" links={[
              ['List your event', '#business'],
              ['Advertise', 'mailto:hello@yoocal.com'],
              ['Partner with us', 'mailto:hello@yoocal.com'],
            ]} />
            <FooterCol title="Cities" links={[
              ['Park City, UT', '/park-city'],
              ['Heber Valley, UT', '/heber'],
              ['Elkhart Lake, WI', '/elkhart-lake'],
              ['Jackson Hole, WY', '/jackson-hole'],
              ['Aspen, CO (soon)', '#signup'],
            ]} />
          </div>
        </div>
        <div style={{
          maxWidth: 1100, margin: '0 auto',
          paddingTop: 24, borderTop: '1px solid rgba(255,255,255,0.08)',
          display: 'flex', justifyContent: 'space-between',
          fontSize: 13, color: 'rgba(255,255,255,0.4)',
        }}>
          <span>© 2026 Yoocal. All rights reserved.</span>
          <span>hello@yoocal.com</span>
        </div>
      </footer>
    </>
  )
}

function FooterCol({ title, links }: { title: string; links: [string, string][] }) {
  return (
    <div>
      <h4 style={{
        color: 'white', fontSize: 13, fontWeight: 600, marginBottom: 12,
        textTransform: 'uppercase', letterSpacing: 0.5,
      }}>{title}</h4>
      {links.map(([label, href]) => (
        <a key={href} href={href} style={{
          display: 'block', color: 'rgba(255,255,255,0.6)',
          fontSize: 14, textDecoration: 'none', marginBottom: 8,
        }}>{label}</a>
      ))}
    </div>
  )
}

const navLink: React.CSSProperties = {
  color: 'var(--text)',
  fontSize: 14, fontWeight: 500,
  textDecoration: 'none',
}

const navLinkOutline: React.CSSProperties = {
  color: 'var(--purple)',
  fontSize: 14, fontWeight: 600,
  textDecoration: 'none',
  padding: '6px 14px',
  border: '1px solid var(--purple)',
  borderRadius: 100,
}

const navCta: React.CSSProperties = {
  background: 'var(--purple)',
  color: 'white',
  fontSize: 14, fontWeight: 600,
  textDecoration: 'none',
  padding: '8px 18px',
  borderRadius: 100,
}
