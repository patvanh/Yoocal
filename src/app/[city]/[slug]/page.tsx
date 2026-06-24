import { notFound, redirect, permanentRedirect } from 'next/navigation'
import type { Metadata } from 'next'
import EventMap from '@/components/EventMap'
import ShareButtons from '@/components/ShareButtons'
import {
  CITY_CONFIG,
  findEvent,
  findEventAnywhere,
  getAllEventsWithCity,
  cityKeyFromSlug,
  eventSlug,
  formatDate,
  getEventsForCity,
  getVenueCoords,
  type YoocalEvent,
  type CityKey,
} from '@/lib/events'

interface Props {
  params: Promise<{ city: string; slug: string }>
}

// Hybrid SSG: pre-build only the next 14 days of events (~600-800 pages).
// Events further out are rendered on demand and cached by Vercel. This
// keeps deploys under ~2 minutes while preserving SEO/perf for the events
// users are most likely to click.
export const dynamicParams = true  // allow on-demand rendering for non-prebuilt slugs

export async function generateStaticParams() {
  const allEvents = getAllEventsWithCity()
  const today = new Date().toISOString().slice(0, 10)
  const horizon = new Date()
  horizon.setDate(horizon.getDate() + 90)  // match sitemap horizon so every listed URL is prebuilt
  const horizonStr = horizon.toISOString().slice(0, 10)

  return allEvents
    .filter((e) => {
      const date = (e.date || '').slice(0, 10)
      return /^\d{4}-\d{2}-\d{2}$/.test(date) && date >= today && date <= horizonStr
    })
    .map((e) => ({
      city: e.citySlug,
      slug: eventSlug(e),
    }))
}

// Generate SEO metadata per event
export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { city, slug } = await params
  const cityKey = cityKeyFromSlug(city)
  if (!cityKey) return {}

  // Mirror the page's not-found handling: an unresolvable slug must not
  // generate successful metadata, or Next prerenders a 200 even though the
  // page calls notFound(). Returning noindex metadata here keeps the route's
  // not-found handling consistent. (The page component still calls
  // notFound() for the actual 404 response.)
  const event = findEvent(cityKey, slug)
  if (!event) return { title: 'Event not found — Yoocal', robots: { index: false, follow: true } }

  const cityConfig = CITY_CONFIG[cityKey]
  const dateStr = formatDate(event.date)
  const title = `${event.title} — ${dateStr} | Yoocal`
  const description = event.description
    ? event.description.slice(0, 155)
    : `${event.title} happening in ${cityConfig.name} on ${dateStr}. Find local events on Yoocal.`

  // Use the event's real image for social previews when it has one (~84% do);
  // otherwise fall back to the branded default. Only accept absolute http(s)
  // URLs — a relative or junk value would break the preview.
  const rawImg = (event.image_url || '').trim()
  const ogImage = /^https?:\/\//.test(rawImg) ? rawImg : 'https://www.yoocal.com/og-image.png'

  return {
    title,
    description,
    openGraph: {
      title,
      description,
      url: `https://www.yoocal.com/${city}/${slug}`,
      type: 'website',
      images: [{ url: ogImage, width: 1200, height: 630 }],
    },
    twitter: {
      card: 'summary_large_image',
      title,
      description,
      images: [ogImage],
    },
    alternates: {
      canonical: `https://www.yoocal.com/${city}/${slug}`,
    },
  }
}

// Category detection (same logic as main calendar)
function getCategories(event: YoocalEvent): string[] {
  const text = ((event.title || '') + ' ' + (event.description || '')).toLowerCase()
  const location = (event.location || '').toLowerCase()
  const cats: string[] = []

  if (/music|concert|band|jazz|live|perform|sing|song|dj|bluegrass|acoustic|folk|rock|country|reggae|blues|indie/.test(text)) cats.push('Music')
  if (/hike|trail|outdoor|bike|ski|snow|mountain|park|nature|climb|kayak|paddle|snowshoe|camp/.test(text)) cats.push('Outdoor')
  if (/food|drink|wine|beer|cocktail|dine|eat|taste|market|farm|chef|brewery|distill|whiskey|spirits|brunch/.test(text)) cats.push('Food & Drink')
  if (/art|gallery|exhibit|museum|paint|sculpt|craft|film|theatre|theater|show|play|dance|screening|improv/.test(text)) cats.push('Arts')
  if (/run|race|marathon|5k|10k|triathlon|relay|cycling|fitness|gym|yoga|pilates|workout|athletic/.test(text)) cats.push('Sports')
  if (/kid|child|family|youth|teen|school|junior|baby|parent|preschool|storytime|story time/.test(text)) cats.push('Family')
  if (/wellness|meditat|breathwork|sound|healing|spa|health|therapy|mindful/.test(text)) cats.push('Wellness')
  if (/community|nonprofit|charity|volunteer|fundrais|lecture|talk|class|learn|workshop|meeting/.test(text)) cats.push('Community')
  if (event.is_free === true || /\bfree\b/.test(text)) cats.push('Free')
  if (event.is_free === false || /\$\d|\bticket(s)?\b/.test(text)) cats.push('Paid')

  return cats.length > 0 ? cats : ['Community']
}

// Related events: same venue first, then same day
function getRelatedEvents(cityKey: CityKey, current: YoocalEvent): YoocalEvent[] {
  const events = getEventsForCity(cityKey)
  const sameVenue = events.filter(e =>
    e.title !== current.title &&
    e.location && current.location &&
    e.location.toLowerCase() === current.location.toLowerCase()
  ).slice(0, 3)

  if (sameVenue.length >= 2) return sameVenue

  const sameDay = events.filter(e =>
    e.title !== current.title &&
    e.date === current.date &&
    !sameVenue.find(s => s.title === e.title)
  ).slice(0, 3 - sameVenue.length)

  return [...sameVenue, ...sameDay]
}

function to24h(time12: string | undefined | null): string {
  if (!time12) return "00:00:00";
  const m = String(time12).trim().match(/^(\d{1,2}):(\d{2})\s*(AM|PM)?$/i);
  if (!m) return "00:00:00";
  let h = parseInt(m[1], 10);
  const min = m[2];
  const ampm = m[3] && m[3].toUpperCase();
  if (ampm === "PM" && h !== 12) h += 12;
  if (ampm === "AM" && h === 12) h = 0;
  return `${String(h).padStart(2, "0")}:${min}:00`;
}
function addOneHourTo24h(time12: string | undefined | null): string {
  const t = to24h(time12);
  const h = parseInt(t.slice(0,2), 10);
  const nh = (h + 1) % 24;
  return `${String(nh).padStart(2,"0")}${t.slice(2)}`;
}

// Build a Google Calendar template URL (no client JS needed — plain link).
// Dates use the same start/end logic as the JSON-LD below.
function googleCalUrl(event: {
  title?: string; date?: string; end_date?: string;
  start_time?: string; end_time?: string;
  description?: string; location?: string;
}): string {
  const compact = (isoDateTime: string) =>
    isoDateTime.replace(/[-:]/g, "").replace(/\.\d+/, "");
  const startIso = event.start_time
    ? `${event.date}T${to24h(event.start_time)}:00`
    : `${event.date}`;
  const endIso = event.end_time
    ? `${event.end_date || event.date}T${to24h(event.end_time)}:00`
    : event.end_date
      ? `${event.end_date}`
      : event.start_time
        ? `${event.date}T${addOneHourTo24h(event.start_time)}:00`
        : `${event.date}`;
  // All-day events (no time) use YYYYMMDD; timed events use YYYYMMDDTHHMMSS.
  const fmt = (iso: string) =>
    iso.includes("T") ? compact(iso) : iso.replace(/-/g, "");
  const dates = `${fmt(startIso)}/${fmt(endIso)}`;
  const params = new URLSearchParams({
    action: "TEMPLATE",
    text: event.title || "Event",
    dates,
    details: (event.description || "").slice(0, 500),
    location: event.location || "",
  });
  return `https://calendar.google.com/calendar/render?${params.toString()}`;
}


export default async function EventPage({ params }: Props) {
  const { city: citySlug, slug } = await params
  const cityKey = cityKeyFromSlug(citySlug)
  if (!cityKey) notFound()

  let event = findEvent(cityKey, slug)
  if (!event) {
    // Event not in this city — search all cities. If found, permanently
    // redirect to the canonical URL. Recovers from URLs Google indexed under
    // the wrong city path (legacy slug bug, no longer producing new bad URLs).
    const cross = findEventAnywhere(slug)
    if (cross) {
      permanentRedirect(`/${cross.citySlug}/${slug}`)
    }
    notFound()
  }

  const city = CITY_CONFIG[cityKey]
  const related = getRelatedEvents(cityKey, event)
  const cats = getCategories(event)
  const dateStr = formatDate(event.date)

  // Get best coordinates: precise venue lookup, then event coords, then city center
  const venueCoords = event.location ? getVenueCoords(event.location) : null
  const mapLat = venueCoords?.[0] ?? event.lat ?? city.center[0]
  const mapLng = venueCoords?.[1] ?? event.lng ?? city.center[1]

  // Schema.org Event structured data
  const breadcrumbSchema = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "Yoocal", item: "https://www.yoocal.com" },
      { "@type": "ListItem", position: 2, name: city.name, item: `https://www.yoocal.com/${citySlug}` },
      { "@type": "ListItem", position: 3, name: event.title, item: `https://www.yoocal.com/${citySlug}/${slug}` },
    ],
  }

  // city.name is stored as "Park City, UT" (locality + region together),
  // which is a malformed addressLocality. Split it so PostalAddress carries a
  // clean addressLocality and a separate addressRegion (required for Google
  // event rich results).
  const _cityParts = city.name.split(",").map((p) => p.trim())
  const cityLocality = _cityParts[0] || city.name
  const cityRegion = _cityParts[1] || undefined

  const schema = {
    "@context": "https://schema.org",
    "@type": "Event",
    name: event.title,
    description: (event.description && event.description.trim()) || event.title,
    ...(/^https?:\/\//.test((event.image_url || "").trim())
      ? { image: [(event.image_url || "").trim()] }
      : {}),
    startDate: event.start_time
      ? `${event.date}T${to24h(event.start_time)}`
      : event.date,
    endDate: event.end_time
      ? `${event.end_date || event.date}T${to24h(event.end_time)}`
      : event.end_date
        ? event.end_date
        : event.start_time
          ? `${event.date}T${addOneHourTo24h(event.start_time)}`
          : event.date,
    location: event.location
      ? {
          "@type": "Place",
          name: event.location,
          address: {
            "@type": "PostalAddress",
            addressLocality: cityLocality,
            ...(cityRegion ? { addressRegion: cityRegion } : {}),
            addressCountry: "US",
          },
        }
      : {
          "@type": "Place",
          name: cityLocality,
          address: {
            "@type": "PostalAddress",
            addressLocality: cityLocality,
            ...(cityRegion ? { addressRegion: cityRegion } : {}),
            addressCountry: "US",
          },
        },
    organizer: {
      "@type": "Organization",
      name: event.source || "Yoocal",
      url: event.source_url || `https://www.yoocal.com/${citySlug}`,
    },
    // Only assert an Offer when we actually know the price (explicitly free, or a
    // parseable amount). Emitting price:"0" for unknown prices would wrongly tell
    // Google the event is free. Omitting offers entirely is valid schema.
    ...(() => {
      if (event.is_free === true) {
        return { offers: { "@type": "Offer", url: event.link || `https://www.yoocal.com/${citySlug}/${slug}`, price: "0", priceCurrency: "USD", availability: "https://schema.org/InStock", validFrom: event.date } };
      }
      const raw = (event.price || "").toString().trim();
      const m = raw.match(/(\d+(?:\.\d+)?)/);
      if (m) {
        return { offers: { "@type": "Offer", url: event.link || `https://www.yoocal.com/${citySlug}/${slug}`, price: m[1], priceCurrency: "USD", availability: "https://schema.org/InStock", validFrom: event.date } };
      }
      return {}; // unknown price -> no offers (don't fabricate free)
    })(),
    url: event.link || `https://www.yoocal.com/${citySlug}/${slug}`,
    isAccessibleForFree: event.is_free === true,
    eventStatus: "https://schema.org/EventScheduled",
    eventAttendanceMode: "https://schema.org/OfflineEventAttendanceMode",
    // Per-event image for Google rich results. Falls back to a branded
    // default when the event has none. 84% of events have a real image_url.
    image: event.image_url || "https://www.yoocal.com/og-image.png",
  }

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbSchema) }}
      />

      {/* NAV */}
      <nav>
        <a href="/" className="nav-logo">
          <div className="nav-dot" />
          yoocal
        </a>
        <div className="nav-links">
          <a href="/about">About</a>
          <a href="/#business">For businesses</a>
          <a
            href="https://forms.groupmail.info/subscribe/yoocal"
            target="_blank"
            rel="noopener noreferrer"
            className="nav-cta"
          >
            Get notified
          </a>
        </div>
      </nav>

      {/* EVENT DETAIL */}
      <main style={{ paddingTop: 64, minHeight: '100vh', background: 'var(--bg)' }}>
        {/* Breadcrumb */}
        <div
          style={{
            background: 'var(--dark)',
            padding: '20px 40px',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            fontSize: 13,
            color: 'rgba(255,255,255,0.4)',
          }}
        >
          <a href="/" style={{ color: 'rgba(255,255,255,0.4)', textDecoration: 'none' }}>
            yoocal
          </a>
          <span>/</span>
          <a
            href={`/?city=${cityKey}`}
            style={{ color: 'rgba(255,255,255,0.4)', textDecoration: 'none' }}
          >
            {city.name}
          </a>
          <span>/</span>
          <span style={{ color: 'rgba(255,255,255,0.65)' }}>{event.title}</span>
        </div>

        {/* Hero */}
        <div
          style={{
            background: 'var(--dark)',
            padding: '48px 40px 56px',
            borderBottom: '1px solid rgba(255,255,255,0.08)',
          }}
        >
          <div style={{ maxWidth: 760, margin: '0 auto' }}>
            {/* Categories */}
            <div className="cal-tags" style={{ marginBottom: 20 }}>
              {cats.slice(0, 3).map((cat) => (
                <span
                  key={cat}
                  className={`cal-tag t-${cat.toLowerCase().replace(/[^a-z]/g, '')}`}
                >
                  {cat}
                </span>
              ))}
            </div>

            {/* Title */}
            <h1
              style={{
                fontFamily: "'DM Serif Display', serif",
                fontSize: 'clamp(28px, 5vw, 48px)',
                color: 'white',
                lineHeight: 1.1,
                marginBottom: 32,
              }}
            >
              {event.title}
            </h1>

            {/* Meta */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {dateStr && (
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 12,
                    fontSize: 16,
                    color: 'rgba(255,255,255,0.85)',
                  }}
                >
                  <span style={{ fontSize: 20 }}>📅</span>
                  <span>{dateStr}</span>
                </div>
              )}
              {event.start_time && (
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 12,
                    fontSize: 16,
                    color: 'rgba(255,255,255,0.85)',
                  }}
                >
                  <span style={{ fontSize: 20 }}>🕐</span>
                  <span>
                    {event.start_time}
                    {event.end_time ? ` – ${event.end_time}` : ''}
                  </span>
                </div>
              )}
              {event.location && (
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 12,
                    fontSize: 16,
                    color: 'rgba(255,255,255,0.85)',
                  }}
                >
                  <span style={{ fontSize: 20 }}>📍</span>
                  <span>
                    {event.location}, {city.name}
                  </span>
                </div>
              )}
              {event.price && (
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 12,
                    fontSize: 16,
                    color: 'rgba(255,255,255,0.85)',
                  }}
                >
                  <span style={{ fontSize: 20 }}>🎟</span>
                  <span>{event.price}</span>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Body */}
        <div style={{ maxWidth: 760, margin: '0 auto', padding: '48px 40px' }}>
          {/* Description */}
          {event.description && (
            <div style={{ marginBottom: 40 }}>
              <h2
                style={{
                  fontFamily: "'DM Serif Display', serif",
                  fontSize: 22,
                  color: 'var(--dark)',
                  marginBottom: 16,
                }}
              >
                About this event
              </h2>
              <p
                style={{
                  fontSize: 16,
                  color: 'var(--muted)',
                  lineHeight: 1.8,
                  fontWeight: 300,
                }}
              >
                {event.description}
              </p>
            </div>
          )}

          {/* CTA */}
          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 48 }}>
            {event.link && (
              <a
                href={event.link}
                target="_blank"
                rel="noopener noreferrer"
                className="btn-primary"
              >
                View event details →
              </a>
            )}
            <a
              href={googleCalUrl(event)}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-secondary"
              style={{ color: 'var(--purple)' }}
            >
              📅 Add to Calendar
            </a>
            <a
              href={`/api/ics/${citySlug}/${slug}`}
              className="btn-secondary"
              style={{ color: 'var(--purple)' }}
            >
              🍎 Apple / .ics
            </a>
            <a href={`/?city=${cityKey}`} className="btn-secondary" style={{ color: 'var(--purple)' }}>
              ← Back to {city.name} events
            </a>
          </div>
          <ShareButtons
            url={`https://www.yoocal.com/${citySlug}/${slug}`}
            title={event.title}
          />

          {/* Map */}
          {event.location && (
            <EventMap
              lat={mapLat}
              lng={mapLng}
              title={event.title}
              location={event.location}
            />
          )}

          {/* Source */}
          {event.source && (
            <p style={{ fontSize: 13, color: 'var(--muted)' }}>
              Source:{' '}
              {event.source_url ? (
                <a
                  href={event.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ color: 'var(--purple)' }}
                >
                  {event.source}
                </a>
              ) : (
                event.source
              )}
            </p>
          )}

          {/* Related events */}
          {related.length > 0 && (
            <div style={{ marginTop: 64 }}>
              <div className="section-label">More in {city.name}</div>
              <h3
                style={{
                  fontFamily: "'DM Serif Display', serif",
                  fontSize: 24,
                  color: 'var(--dark)',
                  marginBottom: 24,
                  marginTop: 8,
                }}
              >
                {related[0].location === event.location && event.location
                  ? `More at ${event.location}`
                  : `Also happening ${dateStr.split(',')[0]}`}
              </h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {related.map((rel) => (
                  <a
                    key={rel.title + rel.date}
                    href={`/${citySlug}/${eventSlug(rel)}`}
                    style={{
                      display: 'flex',
                      gap: 16,
                      padding: '16px 20px',
                      background: 'white',
                      border: '1px solid var(--border)',
                      borderRadius: 16,
                      textDecoration: 'none',
                      transition: 'all 0.2s',
                    }}
                  >
                    <div
                      style={{
                        minWidth: 44,
                        background: 'var(--purple-pale)',
                        borderRadius: 10,
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        justifyContent: 'center',
                        padding: '6px 8px',
                      }}
                    >
                      <span
                        style={{
                          fontSize: 10,
                          fontWeight: 500,
                          textTransform: 'uppercase',
                          color: 'var(--purple)',
                        }}
                      >
                        {new Date(rel.date + 'T12:00:00').toLocaleString('en-US', { month: 'short' })}
                      </span>
                      <span
                        style={{
                          fontSize: 20,
                          fontWeight: 500,
                          color: 'var(--purple)',
                          lineHeight: 1.1,
                        }}
                      >
                        {new Date(rel.date + 'T12:00:00').getDate()}
                      </span>
                    </div>
                    <div>
                      <div
                        style={{ fontSize: 15, fontWeight: 600, color: 'var(--dark)', marginBottom: 4 }}
                      >
                        {rel.title}
                      </div>
                      <div style={{ fontSize: 13, color: 'var(--muted)' }}>
                        {rel.location || city.name}
                      </div>
                    </div>
                  </a>
                ))}
              </div>
            </div>
          )}
        </div>
      </main>

      {/* FOOTER */}
      <footer>
        <div className="footer-top">
          <div>
            <a href="/" className="footer-logo">
              <div className="nav-dot" /> yoocal
            </a>
            <div className="footer-tagline">Your local, everywhere.</div>
          </div>
          <div className="footer-links">
            <div className="footer-col">
              <h4>Product</h4>
              <a href="/#events">Browse events</a>
              <a href="/#how">How it works</a>
              <a href="/#signup">Newsletter</a>
            </div>
            <div className="footer-col">
              <h4>Business</h4>
              <a href="/#business">List your event</a>
              <a href="mailto:hello@yoocal.com">Advertise</a>
            </div>
            <div className="footer-col">
              <h4>Cities</h4>
              <a href="/?city=parkcity">Park City, UT</a>
              <a href="/?city=elkhartlake">Elkhart Lake, WI</a>
            </div>
          </div>
        </div>
        <div className="footer-bottom">
          <span>© 2026 Yoocal. All rights reserved.</span>
          <span>hello@yoocal.com</span>
        </div>
      </footer>
    </>
  )
}
