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

      <div className="hero-wrapper">
        {/* Browse by city pills */}
        <div className="location-bar" id="location-city-chips">
          <span className="loc-label">Browse by city</span>
          <Link href="/park-city" className={`loc-chip${cityKey === "parkcity" ? " active" : ""}`}>📍 Park City, UT</Link>
          <Link href="/elkhart-lake" className={`loc-chip${cityKey === "elkhartlake" ? " active" : ""}`}>📍 Elkhart Lake, WI</Link>
          <Link href="/heber" className={`loc-chip${cityKey === "heber" ? " active" : ""}`}>📍 Heber Valley, UT</Link>
          <Link href="/jackson-hole" className={`loc-chip${cityKey === "jackson" ? " active" : ""}`}>📍 Jackson Hole, WY</Link>
          <a href="#" className="loc-chip" style={{ opacity: 0.5 }}>+ Aspen, CO — coming soon</a>
        </div>
      </div>

      {/* CALENDAR */}
      <section className="calendar-section" id="events" style={{ textAlign: "center" }}>
        <h1 style={{ fontSize: "clamp(40px, 6vw, 68px)", lineHeight: 1.05 }}>
          Things to do in <em>{cityName}</em>
        </h1>
        <p style={{ marginBottom: "40px", marginTop: "12px", fontSize: "18px", color: "rgba(255,255,255,0.7)" }}>
          {cityName} — updated daily
        </p>
        <div style={{ maxWidth: 1100, margin: "0 auto", padding: "0 16px", textAlign: "left" }}>
          <EventsV2Embedded cityKeyProp={cityKey} />
        </div>
      </section>
    </div>
  )
}
