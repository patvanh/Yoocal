import type { Metadata } from "next";
import SiteNav from "@/components/SiteNav";
import SiteFooter from "@/components/SiteFooter";
import CitySwitcher from "@/components/CitySwitcher";
import VenuesGrid, { type VenueWithEvents } from "@/components/VenuesGrid";
import {
  CITY_CONFIG,
  type CityKey,
  loadCityEvents,
} from "@/lib/city-events";
import { eventMatchesVenue, VENUES_BY_CITY } from "@/lib/venues";

// Re-validate every hour so event counts stay fresh
export const revalidate = 3600;

function normalizeCity(raw?: string): CityKey {
  if (raw === "elkhartlake") return "elkhartlake";
  if (raw === "heber") return "heber";
  if (raw === "jackson") return "jackson";
  return "parkcity";
}

export async function generateMetadata(
  { searchParams }: { searchParams: Promise<{ city?: string }> },
): Promise<Metadata> {
  const params = await searchParams;
  const cityKey = normalizeCity(params.city);
  const cfg = CITY_CONFIG[cityKey];
  return {
    title: `${cfg.label} Venues — Theaters, Resorts & Event Spaces | Yoocal`,
    description: `Browse the best venues in ${cfg.label} — Egyptian Theatre, ${cityKey === "parkcity" ? "Deer Valley, Eccles Center, Kimball Arts Center" : "Road America, Osthoff Resort, Siebkens"} — with upcoming events at each.`,
    alternates: { canonical: `https://www.yoocal.com/venues?city=${cityKey}` },
    openGraph: {
      title: `${cfg.label} Venues`,
      description: `Every venue we track in ${cfg.label}, with upcoming events.`,
      url: `https://www.yoocal.com/venues?city=${cityKey}`,
      type: "website",
    },
  };
}

export default async function VenuesPage(
  { searchParams }: { searchParams: Promise<{ city?: string }> },
) {
  const params = await searchParams;
  const cityKey = normalizeCity(params.city);
  const cfg = CITY_CONFIG[cityKey];

  const allEvents = await loadCityEvents(cityKey);

  // Only count upcoming events
  const now = new Date();
  now.setHours(0, 0, 0, 0);
  const upcomingEvents = allEvents.filter((e) => {
    if (!e.date) return false;
    const d = new Date(e.date + "T12:00:00");
    return !Number.isNaN(d.getTime()) && d >= now;
  });

  // Pair each curated venue with its matching events, sorted by date asc
  const venuesWithEvents: VenueWithEvents[] = VENUES_BY_CITY[cityKey].map(
    (venue) => {
      const matching = upcomingEvents
        .filter((ev) => eventMatchesVenue(ev.location, venue))
        .sort(
          (a, b) =>
            new Date(a.date).getTime() - new Date(b.date).getTime(),
        )
        .map((ev) => ({
          title: ev.title,
          date: ev.date,
          end_date: typeof ev.end_date === "string" ? ev.end_date : undefined,
          start_time: ev.start_time,
          end_time: ev.end_time,
          location: ev.location,
          description: ev.description,
          link: ev.link,
          source: ev.source,
          is_free: ev.is_free,
          price: ev.price,
        }));
      return { venue, events: matching };
    },
  )
    // Show venues with the most upcoming events first
    .sort((a, b) => b.events.length - a.events.length);

  const totalEvents = venuesWithEvents.reduce(
    (sum, v) => sum + v.events.length,
    0,
  );

  // ItemList of venues (each a Place with name + address) so this list page
  // is machine-readable to crawlers. Venues have no detail pages, so items
  // carry the venue's PostalAddress rather than a url.
  const itemListSchema = {
    '@context': 'https://schema.org',
    '@type': 'ItemList',
    name: `Venues in ${cfg.label}`,
    numberOfItems: venuesWithEvents.length,
    itemListElement: venuesWithEvents.map((v, i) => ({
      '@type': 'ListItem',
      position: i + 1,
      item: {
        '@type': 'Place',
        name: v.venue.name,
        ...(v.venue.address ? { address: v.venue.address } : {}),
      },
    })),
  };

  return (
    <>
      {venuesWithEvents.length > 0 && (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(itemListSchema) }}
        />
      )}
      <SiteNav activeKey="venues" cityKey={cityKey} />

      <div className="hero">
        <div className="hero-content">
          <div className="hero-eyebrow">📍 {cfg.label}</div>
          <h1>
            {cfg.label}&apos;s best <em>venues.</em>
          </h1>
          <p>
            {venuesWithEvents.length} venues we track in {cfg.label} —{" "}
            {totalEvents > 0
              ? `${totalEvents} upcoming events across them.`
              : "browse and discover what's coming up."}
          </p>
          <CitySwitcher active={cityKey} />
        </div>
      </div>

      <div className="content">
        <VenuesGrid venues={venuesWithEvents} />

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

        .content { max-width: 1200px; margin: 0 auto; padding: 56px 32px 100px; }

        .bottom-cta {
          text-align: center;
          margin-top: 60px;
          padding-top: 32px;
          border-top: 1px solid var(--border);
        }
        .bottom-cta p { font-size: 14px; color: var(--muted); }
        .bottom-cta a { color: var(--purple); font-weight: 600; text-decoration: none; }
        .bottom-cta a:hover { text-decoration: underline; }

        @media (max-width: 600px) {
          .hero { padding: 100px 20px 48px; }
          .content { padding: 40px 16px 64px; }
        }
      `}</style>
    </>
  );
}
