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
    display: "inline-block", padding: "9px 18px", borderRadius: "100px",
    background: "#534AB7", border: "1px solid #6E64C9",
    color: "#ffffff", fontSize: "14px", fontWeight: 600,
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

      {/* BROWSE STRIP — quick links to the per-city intent landing pages.
          These navigate to other pages (unlike the in-hero filter pills,
          which filter the calendar in place), so they use the lighter
          quickLink pill style to read as navigation, not filters. */}
      <div style={{ position: "relative", zIndex: 2, maxWidth: 1100, margin: "0 auto", padding: "78px 16px 6px", display: "flex", flexWrap: "wrap", gap: 10, justifyContent: "center", alignItems: "center" }}>
        <span style={{ color: "rgba(255,255,255,0.75)", fontSize: 13, fontWeight: 600, marginRight: 2 }}>Browse:</span>
        <Link href={`/${citySlug}/this-weekend`} style={quickLink}>This weekend</Link>
        <Link href={`/${citySlug}/free-events`} style={quickLink}>Free events</Link>
        <Link href={`/${citySlug}/concerts`} style={quickLink}>Concerts</Link>
        <Link href={`/${citySlug}/this-month`} style={quickLink}>This month</Link>
      </div>

      {/* CALENDAR */}
      <section className="calendar-section" id="events" style={{ textAlign: "center" }}>
        <div style={{ maxWidth: 1100, margin: "0 auto", padding: "0 16px", textAlign: "left" }}>
          <EventsV2Embedded cityKeyProp={cityKey} />
        </div>
      </section>
    </div>
  )
}
