import type { Metadata } from "next";
import { notFound } from "next/navigation";
import SiteNav from "@/components/SiteNav";
import SiteFooter from "@/components/SiteFooter";
import CitySwitcher from "@/components/CitySwitcher";
import IntentDayList from "@/components/IntentDayList";
import { cityKeyFromSlug, eventSlug } from "@/lib/events";
import { CITY_CONFIG, loadCityEvents, formatLocalISODate } from "@/lib/city-events";

export const revalidate = 3600;
export const dynamicParams = false;

const CITY_SLUGS = ["park-city", "elkhart-lake", "heber", "jackson-hole", "green-lake"] as const;

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
    detailSlug: eventSlug(e),
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
          <IntentDayList events={events} citySlug={city} />
        )}
        <div className="bottom-cta">
          <p>See everything coming up in {cfg.label} \u2192 <a href={`/${city}`}>browse all upcoming events</a></p>
        </div>
      </div>
      <SiteFooter cityLabel={cfg.label} />
      <style>{`
        body { font-family: 'DM Sans', sans-serif; background: #1a1830; color: #fff; overflow-x: hidden; }
        .hero {
          background: linear-gradient(135deg, #1a1830 0%, #2a2450 55%, #1f1b3a 100%);
          padding: 110px 32px 64px; text-align: center; position: relative; overflow: hidden;
        }
        .hero::after {
          content: ''; position: absolute; inset: 0;
          background: radial-gradient(ellipse 70% 90% at 50% -10%, rgba(123,92,255,0.30) 0%, transparent 60%);
          pointer-events: none;
        }
        .hero-content { position: relative; z-index: 2; max-width: 720px; margin: 0 auto; }
        .hero-eyebrow {
          display: inline-flex; align-items: center; gap: 8px;
          background: rgba(255,255,255,0.1); color: rgba(255,255,255,0.92);
          font-size: 12px; font-weight: 700; padding: 7px 16px; border-radius: 100px;
          margin-bottom: 22px; letter-spacing: 0.4px; border: 1px solid rgba(255,255,255,0.16);
          text-transform: uppercase;
        }
        .hero h1 {
          font-family: 'DM Serif Display', serif; font-size: clamp(38px, 5.5vw, 58px);
          color: white; line-height: 1.04; margin: 0 0 14px;
        }
        .hero h1 em { font-style: italic; color: #9b8ff0; }
        .hero p { font-size: 17px; color: rgba(255,255,255,0.62); line-height: 1.55; max-width: 540px; margin: 0 auto 26px; }
        .content {
          max-width: 880px; margin: -32px auto 0; padding: 0 20px 100px;
          position: relative; z-index: 3;
        }
        .empty {
          text-align: center; padding: 72px 24px; background: rgba(255,255,255,0.04);
          border-radius: 22px; border: 1px solid rgba(255,255,255,0.10);
          box-shadow: none;
        }
        .empty-emoji { font-size: 46px; margin-bottom: 14px; }
        .empty h2 { font-family: 'DM Serif Display', serif; font-size: 26px; margin-bottom: 10px; color: #fff; }
        .empty p { color: rgba(255,255,255,0.60); font-size: 16px; }
        .empty a { color: #9b8ff0; font-weight: 600; }
        .bottom-cta { text-align: center; margin-top: 44px; padding-top: 0; border-top: none; }
        .bottom-cta p { font-size: 14px; color: rgba(255,255,255,0.50); }
        .bottom-cta a { color: #9b8ff0; font-weight: 700; text-decoration: none; }
        .bottom-cta a:hover { text-decoration: underline; }
        @media (max-width: 600px) {
          .hero { padding: 92px 18px 56px; }
          .content { padding: 0 14px 64px; }
        }
        /* compact hero — minimal slim bar */
        .hero { padding: 78px 24px 18px !important; min-height: 0 !important; }
        .hero-eyebrow { display: none !important; }
        .hero h1 { font-size: clamp(24px, 3vw, 34px) !important; margin: 0 0 16px !important; line-height: 1.06 !important; }
        .hero p { display: none !important; }
        .content { margin-top: 6px !important; }
      `}</style>
    </>
  );
}
