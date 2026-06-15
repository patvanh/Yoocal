"use client"

import Link from "next/link"
import { EventsV2Embedded } from "@/components/CalendarClient"
import SiteNav from "@/components/SiteNav"

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
      <SiteNav cityKey={cityKey as any} />



      {/* CALENDAR */}
      <section className="calendar-section" id="events" style={{ textAlign: "center" }}>
        <div style={{ maxWidth: 1100, margin: "0 auto", padding: "0 16px", textAlign: "left" }}>
          <EventsV2Embedded cityKeyProp={cityKey} />
        </div>
      </section>
    </div>
  )
}
