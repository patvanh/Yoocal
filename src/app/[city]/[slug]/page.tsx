import { notFound } from 'next/navigation'
import type { Metadata } from 'next'
import Link from 'next/link'
import {
  CITY_CONFIG,
  findEvent,
  getAllEventsWithCity,
  cityKeyFromSlug,
  eventSlug,
  formatDate,
  getEventsForCity,
  type YoocalEvent,
  type CityKey,
} from '@/lib/events'

interface Props {
  params: Promise<{ city: string; slug: string }>
}

// Pre-generate all event pages at build time
export async function generateStaticParams() {
  const allEvents = getAllEventsWithCity()
  return allEvents.map((e) => ({
    city: e.citySlug,
    slug: eventSlug(e),
  }))
}

// Generate SEO metadata per event
export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { city, slug } = await params
  const cityKey = cityKeyFromSlug(city)
  if (!cityKey) return {}

  const event = findEvent(cityKey, slug)
  if (!event) return {}

  const cityConfig = CITY_CONFIG[cityKey]
  const dateStr = formatDate(event.date)
  const title = `${event.title} — ${dateStr} | Yoocal`
  const description = event.description
    ? event.description.slice(0, 155)
    : `${event.title} happening in ${cityConfig.name} on ${dateStr}. Find local events on Yoocal.`

  return {
    title,
    description,
    openGraph: {
      title,
      description,
      url: `https://www.yoocal.com/${city}/${slug}`,
      images: [{ url: '/og-image.png', width: 1200, height: 630 }],
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

// Related events from same city, same day or nearby
function getRelatedEvents(cityKey: CityKey, current: YoocalEvent): YoocalEvent[] {
  const events = getEventsForCity(cityKey)
  return events
    .filter(e => e.title !== current.title && e.date === current.date)
    .slice(0, 3)
}

export default async function EventPage({ params }: Props) {
  const { city: citySlug, slug } = await params
  const cityKey = cityKeyFromSlug(citySlug)
  if (!cityKey) notFound()

  const event = findEvent(cityKey, slug)
  if (!event) notFound()

  const city = CITY_CONFIG[cityKey]
  const related = getRelatedEvents(cityKey, event)
  const cats = getCategories(event)
  const dateStr = formatDate(event.date)

  // Schema.org Event structured data
  const schema = {
    '@context': 'https://schema.org',
    '@type': 'Event',
    name: event.title,
    description: event.description || undefined,
    startDate: event.start_time
      ? `${event.date}T${event.start_time}`
      : event.date,
    endDate: event.end_time
      ? `${event.date}T${event.end_time}`
      : undefined,
    location: event.location
      ? {
          '@type': 'Place',
          name: event.location,
          address: {
            '@type': 'PostalAddress',
            addressLocality: city.name,
          },
        }
      : undefined,
    organizer: event.source
      ? { '@type': 'Organization', name: event.source }
      : undefined,
    url: event.link || `https://www.yoocal.com/${citySlug}/${slug}`,
    isAccessibleForFree: event.is_free ?? undefined,
    eventStatus: 'https://schema.org/EventScheduled',
    eventAttendanceMode: 'https://schema.org/OfflineEventAttendanceMode',
    image: 'https://www.yoocal.com/og-image.png',
  }

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
      />

      {/* NAV */}
      <nav>
        <a href="/" className="nav-logo">
          <div className="nav-dot" />
          yoocal
        </a>
        <div className="nav-links">
          <a href="/about-yoocal.html">About</a>
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
            <a href={`/?city=${cityKey}`} className="btn-secondary" style={{ color: 'var(--purple)' }}>
              ← Back to {city.name} events
            </a>
          </div>

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
                Also happening {dateStr.split(',')[0]}
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
