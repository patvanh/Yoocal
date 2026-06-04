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

// Window: today through the last day of the current month (calendar month, to
// match "events in [city] [Month] [Year]" searches).
function monthWindow(): { startStr: string; endStr: string; label: string } {
  const now = new Date();
  const start = now;
  const end = new Date(now.getFullYear(), now.getMonth() + 1, 0);
  const label = now.toLocaleDateString("en-US", { month: "long", year: "numeric" });
  return { startStr: formatLocalISODate(start), endStr: formatLocalISODate(end), label };
}

export async function generateMetadata(
  { params }: { params: Promise<{ city: string }> },
): Promise<Metadata> {
  const { city } = await params;
  const cityKey = cityKeyFromSlug(city);
  if (!cityKey) return {};
  const cfg = CITY_CONFIG[cityKey];
  const { label } = monthWindow();
  const url = `https://www.yoocal.com/${city}/this-month`;
  return {
    title: `${cfg.label} Events in ${label} \u2014 Things to Do This Month | Yoocal`,
    description: `Everything happening in ${cfg.label} this month (${label}) \u2014 concerts, festivals, races, food, and family events. Updated daily.`,
    alternates: { canonical: url },
    openGraph: {
      title: `${cfg.label} Events in ${label}`,
      description: `Things to do in ${cfg.label} this month \u2014 updated daily.`,
      url,
      type: "website",
    },
  };
}

export default async function CityThisMonthPage(
  { params }: { params: Promise<{ city: string }> },
) {
  const { city } = await params;
  const cityKey = cityKeyFromSlug(city);
  if (!cityKey) notFound();
  const cfg = CITY_CONFIG[cityKey];

  const { startStr, endStr, label } = monthWindow();
  const all = await loadCityEvents(cityKey);
  const inMonth = all
    .filter((e) => {
      const start = (e.date || "").slice(0, 10);
      const end = ((typeof e.end_date === "string" ? e.end_date : "") || e.date || "").slice(0, 10);
      return start <= endStr && end >= startStr;
    })
    .sort((a, b) => (a.date || "").localeCompare(b.date || ""));

  const events = inMonth.map((e) => ({
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
      <SiteNav cityKey={cityKey} />
      <div className="hero">
        <div className="hero-content">
          <div className="hero-eyebrow">{label}</div>
          <h1>Things to do in <em>{cfg.label}</em> this month.</h1>
          <p>
            {events.length > 0
              ? `${events.length} events in ${cfg.label} through the end of ${label}.`
              : "Updated daily from every source that matters."}
          </p>
          <CitySwitcher active={cityKey} />
        </div>
      </div>
      <div className="content">
        {events.length === 0 ? (
          <div className="empty">
            <div className="empty-emoji">{"\ud83d\udcc5"}</div>
            <h2>No events on file for the rest of this month</h2>
            <p>Our scraper runs daily \u2014 check back soon, or browse the full <a href={`/${city}`}>{cfg.label} calendar</a>.</p>
          </div>
        ) : (
          <WeekendDayList events={events} />
        )}
        <div className="bottom-cta">
          <p>See everything coming up in {cfg.label} \u2192 <a href={`/${city}`}>browse all upcoming events</a></p>
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
