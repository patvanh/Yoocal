import { getEventsForCity, slugify, CITY_CONFIG, type CityKey } from "@/lib/events"

/**
 * CityHubServer — compact server-rendered canonical content for a city hub.
 *
 * The interactive calendar (EventsV2Embedded) fetches its data in the browser,
 * so crawlers/no-JS visitors see nothing from it. This renders the real,
 * indexable essentials server-side: a single H1, a dated near-term summary, and
 * a handful of upcoming-event highlight links — enough for citability and a true
 * H1 without burying the interactive app (which owns the full list below).
 * Separate render tree: no hydration coupling with the client app.
 */

function fmtDate(iso: string): string {
  const d = new Date(iso + "T00:00:00")
  if (isNaN(d.getTime())) return ""
  return d.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" })
}

export default function CityHubServer({ cityKey }: { cityKey: CityKey }) {
  const cfg = CITY_CONFIG[cityKey]
  const cityName = cfg.name.replace(/,.*$/, "").trim()

  const now = new Date()
  const today = now.toISOString().slice(0, 10)
  const in30 = new Date(now.getTime() + 30 * 86400000).toISOString().slice(0, 10)

  const upcoming = getEventsForCity(cityKey)
    .filter((e) => /^\d{4}-\d{2}-\d{2}/.test(e.date || "") && (e.date || "").slice(0, 10) >= today)
    .sort((a, b) => (a.date || "").localeCompare(b.date || ""))

  if (upcoming.length === 0) return null

  // Near-term count (next 30 days) is the meaningful "what's going on" number,
  // not the full year-plus horizon.
  const next30 = upcoming.filter((e) => (e.date || "").slice(0, 10) <= in30).length
  const highlights = upcoming.slice(0, 6)

  return (
    <section className="hub-server" aria-label={`Upcoming events in ${cityName}`}>
      <div className="hub-server-inner">
        <h1 className="hub-server-h1">Things to do in {cityName}</h1>
        <p className="hub-server-summary">
          {next30} {next30 === 1 ? "event" : "events"} in {cfg.label} over the next 30 days —
          concerts, festivals, races, food, and family events, updated daily. Browse the full
          calendar below, or jump to a highlight:
        </p>
        <ul className="hub-server-list">
          {highlights.map((e, i) => {
            const href = `/${cfg.slug}/${slugify(e.title)}-${(e.date || "").slice(0, 10)}`
            const venue = e.venue_name || e.location || ""
            return (
              <li key={i} className="hub-server-item">
                <a href={href}>
                  <span className="hub-server-date">{fmtDate((e.date || "").slice(0, 10))}{e.start_time ? ` · ${e.start_time}` : ""}</span>
                  <span className="hub-server-title">{e.title}</span>
                  {venue ? <span className="hub-server-venue">{venue}</span> : null}
                </a>
              </li>
            )
          })}
        </ul>
      </div>

      <style>{`
        .hub-server { background: #faf9ff; padding: 96px 16px 16px; }
        .hub-server-inner { max-width: 1100px; margin: 0 auto; }
        .hub-server-h1 { font-family: 'DM Serif Display', serif; font-size: 30px; line-height: 1.12; color: #1e1b3a; margin: 0 0 10px; }
        .hub-server-summary { font-size: 15px; line-height: 1.6; color: #5b5676; margin: 0 0 18px; max-width: 720px; }
        .hub-server-list { list-style: none; padding: 0; margin: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 8px; }
        .hub-server-item a { display: flex; flex-direction: column; gap: 2px; padding: 10px 12px; background: #fff; border: 1px solid #ece8fa; border-radius: 10px; text-decoration: none; transition: border-color 0.15s; }
        .hub-server-item a:hover { border-color: #b9aef5; }
        .hub-server-date { font-size: 11px; font-weight: 700; color: #7b5cff; }
        .hub-server-title { font-size: 14px; font-weight: 600; color: #1e1b3a; line-height: 1.25; }
        .hub-server-venue { font-size: 12px; color: #8a85a6; }
        @media (max-width: 640px) { .hub-server { padding: 84px 16px 12px; } .hub-server-h1 { font-size: 25px; } }
      `}</style>
    </section>
  )
}
