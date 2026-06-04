import type { Metadata } from "next";
import { notFound } from "next/navigation";
import SiteNav from "@/components/SiteNav";
import SiteFooter from "@/components/SiteFooter";
import CitySwitcher from "@/components/CitySwitcher";
import IntentDayList from "@/components/IntentDayList";
import { cityKeyFromSlug } from "@/lib/events";
import {
  CITY_CONFIG,
  computeWeekendWindow,
  groupEventsByDay,
  loadCityEvents,
} from "@/lib/city-events";

export const revalidate = 3600;
export const dynamicParams = false;

const CITY_SLUGS = ["park-city", "elkhart-lake", "heber", "jackson-hole"] as const;

export function generateStaticParams() {
  return CITY_SLUGS.map((city) => ({ city }));
}

export async function generateMetadata(
  { params }: { params: Promise<{ city: string }> },
): Promise<Metadata> {
  const { city } = await params;
  const cityKey = cityKeyFromSlug(city);
  if (!cityKey) return {};
  const cfg = CITY_CONFIG[cityKey];
  const url = `https://www.yoocal.com/${city}/this-weekend`;
  return {
    title: `This Weekend in ${cfg.label} \u2014 Things to do Friday, Saturday, Sunday | Yoocal`,
    description: `Everything happening this weekend in ${cfg.label}. Live music, races, festivals, food, and family events \u2014 updated daily.`,
    alternates: { canonical: url },
    openGraph: {
      title: `This Weekend in ${cfg.label}`,
      description: `Things to do this Friday, Saturday, and Sunday in ${cfg.label}.`,
      url,
      type: "website",
    },
  };
}

export default async function CityWeekendPage(
  { params }: { params: Promise<{ city: string }> },
) {
  const { city } = await params;
  const cityKey = cityKeyFromSlug(city);
  if (!cityKey) notFound();
  const cfg = CITY_CONFIG[cityKey];

  const allEvents = await loadCityEvents(cityKey);
  const weekendWindow = computeWeekendWindow();
  const grouped = groupEventsByDay(allEvents, weekendWindow);
  const total = grouped.reduce((sum, g) => sum + g.events.length, 0);

  return (
    <>
      <SiteNav activeKey="weekend" cityKey={cityKey} />
      <div className="hero">
        <div className="hero-content">
          <div className="hero-eyebrow">This Weekend</div>
          <h1>Everything happening this <em>weekend.</em></h1>
          <p>
            {grouped[0].day.label.split(",")[0]},{" "}
            {grouped[1].day.label.split(",")[0]}, and{" "}
            {grouped[2].day.label.split(",")[0]} in {cfg.label}.{" "}
            {total > 0 ? `${total} events on the calendar.` : "Updated daily from every source that matters."}
          </p>
          <CitySwitcher active={cityKey} />
        </div>
      </div>
      <div className="content">
        {total === 0 ? (
          <div className="empty">
            <div className="empty-emoji">{"\ud83c\udf19"}</div>
            <h2>No events on file for this weekend yet</h2>
            <p>Our scraper runs daily \u2014 check back soon, or browse the full <a href={`/${city}`}>{cfg.label} calendar</a>.</p>
          </div>
        ) : (
          <IntentDayList events={grouped.flatMap((bucket) => bucket.events.map((e) => ({
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
          })))} />
        )}
        <div className="bottom-cta">
          <p>See the full {cfg.label} calendar \u2192 <a href={`/${city}`}>browse all upcoming events</a></p>
        </div>
      </div>
      <SiteFooter cityLabel={cfg.label} />
      <style>{`
        body { font-family: 'DM Sans', sans-serif; background: #f4f2f9; color: #1a1830; overflow-x: hidden; }
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
          text-align: center; padding: 72px 24px; background: white;
          border-radius: 22px; border: 1px solid rgba(26,24,48,0.08);
          box-shadow: 0 12px 40px rgba(26,24,48,0.10);
        }
        .empty-emoji { font-size: 46px; margin-bottom: 14px; }
        .empty h2 { font-family: 'DM Serif Display', serif; font-size: 26px; margin-bottom: 10px; }
        .empty p { color: #6b6880; font-size: 16px; }
        .empty a { color: #6b61d6; font-weight: 600; }
        .bottom-cta { text-align: center; margin-top: 44px; padding-top: 0; border-top: none; }
        .bottom-cta p { font-size: 14px; color: #6b6880; }
        .bottom-cta a { color: #6b61d6; font-weight: 700; text-decoration: none; }
        .bottom-cta a:hover { text-decoration: underline; }
        @media (max-width: 600px) {
          .hero { padding: 92px 18px 56px; }
          .content { padding: 0 14px 64px; }
        }
      `}</style>
    </>
  );
}
