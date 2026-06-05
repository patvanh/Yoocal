"use client"

import Link from "next/link"
import { EventsV2Embedded } from "@/components/CalendarClient"

const CITY_NAMES: Record<string, string> = {
  parkcity: "Park City",
  heber: "Heber Valley",
  jackson: "Jackson Hole",
  elkhartlake: "Elkhart Lake",
}

/**
 * Clean-URL city landing page (e.g. /park-city). Renders the calendar-first
 * layout for SEO: header, browse-by-city pills, then the calendar for this
 * specific city. Distinct from the legacy CalendarClient which reads ?city=.
 */
export default function CityLanding({ citySlug, cityKey }: { citySlug: string; cityKey: string }) {
  const cityName = CITY_NAMES[cityKey] || "Local"
  const quickLink: React.CSSProperties = {
    display: "inline-block", padding: "8px 16px", borderRadius: "100px",
    background: "rgba(255,255,255,0.08)", border: "1px solid rgba(255,255,255,0.15)",
    color: "rgba(255,255,255,0.9)", fontSize: "14px", fontWeight: 600,
    textDecoration: "none",
  }
  return (
    <div style={{ background: '#1a1830', minHeight: '100vh' }}>
      {/* NAV */}
      <nav>
        <a href="/" className="nav-logo"><div className="nav-dot" /> yoocal</a>
        <div className="nav-links">
          <a href="/about">About</a>
          <a href="/for-businesses">For businesses</a>
          <a href="https://forms.groupmail.info/subscribe/yoocal" target="_blank" rel="noopener noreferrer" className="nav-cta">Get notified</a>
        </div>
      </nav>


      {/* CALENDAR */}
      <section className="calendar-section" id="events" style={{ textAlign: "center" }}>
        <div style={{ maxWidth: 1100, margin: "0 auto", padding: "0 16px", textAlign: "left" }}>
          <EventsV2Embedded cityKeyProp={cityKey} />
        </div>
      </section>
    </div>
  )
}
