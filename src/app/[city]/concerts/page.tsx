import type { Metadata } from "next";
import { notFound } from "next/navigation";
import SiteNav from "@/components/SiteNav";
import SiteFooter from "@/components/SiteFooter";
import CitySwitcher from "@/components/CitySwitcher";
import WeekendDayList from "@/components/WeekendDayList";
import { cityKeyFromSlug } from "@/lib/events";
import { CITY_CONFIG, loadCityEvents, formatLocalISODate } from "@/lib/city-events";

export const revalidate = 3600;
export const dynamicParams = false;

const CITY_SLUGS = ["park-city", "elkhart-lake", "heber", "jackson-hole"] as const;

export function generateStaticParams() {
  return CITY_SLUGS.map((city) => ({ city }));
}

function isMusic(e: unknown): boolean {
  const ev = e as { filter_categories?: unknown; categories?: unknown };
  const fc = Array.isArray(ev.filter_categories)
    ? (ev.filter_categories as string[])
    : Array.isArray(ev.categories)
      ? (ev.categories as string[])
      : [];
  return fc.includes("Music");
}

export async function generateMetadata(
  { params }: { params: Promise<{ city: string }> },
): Promise<Metadata> {
  const { city } = await params;
  const cityKey = cityKeyFromSlug(city);
  if (!cityKey) return {};
  const cfg = CITY_CONFIG[cityKey];
  const url = `https://www.yoocal.com/${city}/concerts`;
  return {
    title: `Concerts & Live Music in ${cfg.label} \u2014 Upcoming Shows | Yoocal`,
    description: `Upcoming concerts and live music in ${cfg.label} \u2014 festivals, concert series, and shows. Updated daily.`,
    alternates: { canonical: url },
    openGraph: {
      title: `Concerts & Live Music in ${cfg.label}`,
      description: `Upcoming concerts and live music in ${cfg.label} \u2014 updated daily.`,
      url,
      type: "website",
    },
  };
}

export default async function CityConcertsPage(
  { params }: { params: Promise<{ city: string }> },
) {
  const { city } = await params;
  const cityKey = cityKeyFromSlug(city);
  if (!cityKey) notFound();
  const cfg = CITY_CONFIG[cityKey];

  const todayStr = formatLocalISODate(new Date());
  const all = await loadCityEvents(cityKey);
  const shows = all
    .filter((e) => isMusic(e))
    .filter((e) => ((typeof e.end_date === "string" ? e.end_date : "") || e.date || "") >= todayStr)
    .sort((a, b) => (a.date || "").localeCompare(b.date || ""));

  const events = shows.map((e) => ({
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
    categories: Array.isArray(e.categories) ? (e.categories as string[]) : undefined,
  }));

  return (
    <>
      <SiteNav activeKey="concerts" cityKey={cityKey} />
      <div className="hero">
        <div className="hero-content">
          <div className="hero-eyebrow">Concerts & Live Music</div>
          <h1>Concerts & live music in <em>{cfg.label}.</em></h1>
          <p>
            {events.length > 0
              ? `${events.length} upcoming concerts and live music events.`
              : "Updated daily from every source that matters."}
          </p>
          <CitySwitcher active={cityKey} />
        </div>
      </div>
      <div className="content">
        {events.length === 0 ? (
          <div className="empty">
            <div className="empty-emoji">{"\ud83c\udfb5"}</div>
            <h2>No concerts on file right now</h2>
            <p>Our scraper runs daily \u2014 check back soon, or browse the full <a href={`/${city}`}>{cfg.label} calendar</a>.</p>
          </div>
        ) : (
          <WeekendDayList events={events} />
        )}
        <div className="bottom-cta">
          <p>See everything happening in {cfg.label} \u2192 <a href={`/${city}`}>browse all upcoming events</a></p>
        </div>
      </div>
      <SiteFooter cityLabel={cfg.label} />
      <style>{`
        body { font-family: 'DM Sans', sans-serif; background: var(--bg); color: var(--text); overflow-x: hidden; }
        .hero { background: var(--dark); padding: 120px 80px 64px; position: relative; overflow: hidden; text-align: center; }
        .hero::before { content: ''; position: absolute; inset: 0; background: radial-gradient(ellipse 80% 60% at 50% 100%, rgba(83,74,183,0.4) 0%, transparent 70%); }
        .hero-content { position: relative; z-index: 2; max-width: 760px; margin: 0 auto; }
        .hero-eyebrow { display: inline-flex; align-items: center; gap: 8px; background: rgba(255,255,255,0.1); color: rgba(255,255,255,0.9); font-size: 12px; font-weight: 600; padding: 6px 16px; border-radius: 100px; margin-bottom: 24px; letter-spacing: 0.5px; border: 1px solid rgba(255,255,255,0.15); }
        .hero h1 { font-family: 'DM Serif Display', serif; font-size: clamp(36px, 5.5vw, 64px); color: white; line-height: 1.05; margin-bottom: 18px; }
        .hero h1 em { font-style: italic; color: #9b8ff0; }
        .hero p { font-size: 17px; color: rgba(255,255,255,0.6); line-height: 1.6; max-width: 540px; margin: 0 auto; }
        .content { max-width: 900px; margin: 0 auto; padding: 56px 32px 100px; }
        .empty { text-align: center; padding: 80px 24px; background: white; border-radius: 24px; border: 1px solid var(--border); }
        .empty-emoji { font-size: 48px; margin-bottom: 16px; }
        .empty h2 { font-family: 'DM Serif Display', serif; font-size: 28px; margin-bottom: 12px; }
        .empty p { color: var(--muted); font-size: 16px; }
        .empty a { color: var(--purple); font-weight: 600; }
        .bottom-cta { text-align: center; margin-top: 40px; padding-top: 32px; border-top: 1px solid var(--border); }
        .bottom-cta p { font-size: 14px; color: var(--muted); }
        .bottom-cta a { color: var(--purple); font-weight: 600; text-decoration: none; }
        .bottom-cta a:hover { text-decoration: underline; }
        @media (max-width: 600px) { .hero { padding: 100px 20px 48px; } .content { padding: 40px 16px 64px; } }
      `}</style>
    </>
  );
}
