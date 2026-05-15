import type { Metadata } from "next";
import SiteNav from "@/components/SiteNav";
import SiteFooter from "@/components/SiteFooter";
import CitySwitcher from "@/components/CitySwitcher";
import WeekendDayList from "@/components/WeekendDayList";
import {
  CITY_CONFIG,
  type CityKey,
  computeWeekendWindow,
  groupEventsByDay,
  loadCityEvents,
} from "@/lib/city-events";

// Re-validate every hour so "this weekend" stays fresh.
export const revalidate = 3600;

export async function generateMetadata(
  { searchParams }: { searchParams: Promise<{ city?: string }> },
): Promise<Metadata> {
  const params = await searchParams;
  const cityKey = normalizeCity(params.city);
  const cfg = CITY_CONFIG[cityKey];
  return {
    title: `This Weekend in ${cfg.label} — Things to do Friday, Saturday, Sunday | Yoocal`,
    description: `Everything happening this weekend in ${cfg.label}. Live music, races, festivals, food, family events — updated daily.`,
    alternates: {
      canonical: `https://www.yoocal.com/this-weekend?city=${cityKey}`,
    },
    openGraph: {
      title: `This Weekend in ${cfg.label}`,
      description: `Things to do this Friday, Saturday, and Sunday in ${cfg.label}.`,
      url: `https://www.yoocal.com/this-weekend?city=${cityKey}`,
      type: "website",
    },
  };
}

function normalizeCity(raw?: string): CityKey {
  if (raw === "elkhartlake") return "elkhartlake";
  return "parkcity";
}

export default async function ThisWeekendPage(
  { searchParams }: { searchParams: Promise<{ city?: string }> },
) {
  const params = await searchParams;
  const cityKey = normalizeCity(params.city);
  const cfg = CITY_CONFIG[cityKey];

  const allEvents = await loadCityEvents(cityKey);
  const window = computeWeekendWindow();
  const grouped = groupEventsByDay(allEvents, window);
  const total = grouped.reduce((sum, g) => sum + g.events.length, 0);

  return (
    <>
      <SiteNav activeKey="weekend" cityKey={cityKey} />

      <div className="hero">
        <div className="hero-content">
          <div className="hero-eyebrow">📅 This Weekend</div>
          <h1>
            Everything happening this <em>weekend.</em>
          </h1>
          <p>
            {grouped[0].day.label.split(",")[0]},{" "}
            {grouped[1].day.label.split(",")[0]}, and{" "}
            {grouped[2].day.label.split(",")[0]} in {cfg.label}.{" "}
            {total > 0
              ? `${total} events on the calendar.`
              : "Updated daily from every source that matters."}
          </p>
          <CitySwitcher active={cityKey} />
        </div>
      </div>

      <div className="content">
        {total === 0 ? (
          <div className="empty">
            <div className="empty-emoji">🌙</div>
            <h2>No events on file for this weekend yet</h2>
            <p>
              Our scraper runs daily — check back soon, or browse the full{" "}
              <a href={`/?city=${cityKey}`}>{cfg.label} calendar</a>.
            </p>
          </div>
        ) : (
          grouped.map((bucket) => (
            <section key={bucket.day.iso} className="day-section">
              <div className="day-header">
                <h2>{bucket.day.label}</h2>
                <span className="day-count">
                  {bucket.events.length}{" "}
                  {bucket.events.length === 1 ? "event" : "events"}
                </span>
              </div>

              {bucket.events.length === 0 ? (
                <div className="day-empty">
                  No events on the calendar for this day.
                </div>
              ) : (
                <WeekendDayList
                  events={bucket.events.map((e) => ({
                    title: e.title,
                    date: e.date,
                    end_date: typeof e.end_date === "string" ? e.end_date : undefined,
                    start_time: e.start_time,
                    end_time: e.end_time,
                    location: e.location,
                    description: e.description,
                    link: e.link,
                    source: e.source,
                    is_free: e.is_free,
                    price: e.price,
                    categories: Array.isArray(e.categories)
                      ? (e.categories as string[])
                      : undefined,
                  }))}
                />
              )}
            </section>
          ))
        )}

        <div className="bottom-cta">
          <p>
            See the full {cfg.label} calendar →{" "}
            <a href={`/?city=${cityKey}`}>browse all upcoming events</a>
          </p>
        </div>
      </div>

      <SiteFooter cityLabel={cfg.label} />

      <style>{`
        body { font-family: 'DM Sans', sans-serif; background: var(--bg); color: var(--text); overflow-x: hidden; }

        .hero {
          background: var(--dark);
          padding: 120px 80px 64px;
          position: relative;
          overflow: hidden;
          text-align: center;
        }
        .hero::before {
          content: ''; position: absolute; inset: 0;
          background: radial-gradient(ellipse 80% 60% at 50% 100%, rgba(83,74,183,0.4) 0%, transparent 70%);
        }
        .hero-content { position: relative; z-index: 2; max-width: 760px; margin: 0 auto; }
        .hero-eyebrow {
          display: inline-flex; align-items: center; gap: 8px;
          background: rgba(255,255,255,0.1); color: rgba(255,255,255,0.9);
          font-size: 12px; font-weight: 600; padding: 6px 16px;
          border-radius: 100px; margin-bottom: 24px;
          letter-spacing: 0.5px; border: 1px solid rgba(255,255,255,0.15);
        }
        .hero h1 {
          font-family: 'DM Serif Display', serif;
          font-size: clamp(36px, 5.5vw, 64px);
          color: white; line-height: 1.05; margin-bottom: 18px;
        }
        .hero h1 em { font-style: italic; color: #9b8ff0; }
        .hero p {
          font-size: 17px; color: rgba(255,255,255,0.6);
          line-height: 1.6; max-width: 540px; margin: 0 auto;
        }

        .content { max-width: 900px; margin: 0 auto; padding: 56px 32px 100px; }

        .empty {
          text-align: center;
          padding: 80px 24px;
          background: white;
          border-radius: 24px;
          border: 1px solid var(--border);
        }
        .empty-emoji { font-size: 48px; margin-bottom: 16px; }
        .empty h2 {
          font-family: 'DM Serif Display', serif;
          font-size: 28px; margin-bottom: 12px;
        }
        .empty p { color: var(--muted); font-size: 16px; }
        .empty a { color: var(--purple); font-weight: 600; }

        .day-section { margin-bottom: 48px; }
        .day-header {
          display: flex; align-items: baseline;
          justify-content: space-between; gap: 12px;
          margin-bottom: 18px; padding-bottom: 12px;
          border-bottom: 2px solid var(--border);
        }
        .day-header h2 {
          font-family: 'DM Serif Display', serif;
          font-size: 28px; line-height: 1.1;
        }
        .day-count {
          font-size: 13px; font-weight: 600;
          color: var(--purple); text-transform: uppercase;
          letter-spacing: 0.5px;
        }
        .day-empty {
          padding: 32px;
          color: var(--muted); font-size: 15px;
          text-align: center;
          background: rgba(255,255,255,0.5);
          border-radius: 16px;
          border: 1px dashed var(--border);
        }

        .bottom-cta {
          text-align: center;
          margin-top: 40px;
          padding-top: 32px;
          border-top: 1px solid var(--border);
        }
        .bottom-cta p {
          font-size: 14px;
          color: var(--muted);
        }
        .bottom-cta a {
          color: var(--purple);
          font-weight: 600;
          text-decoration: none;
        }
        .bottom-cta a:hover { text-decoration: underline; }

        @media (max-width: 600px) {
          .hero { padding: 100px 20px 48px; }
          .content { padding: 40px 16px 64px; }
          .day-header h2 { font-size: 22px; }
        }
      `}</style>
    </>
  );
}
