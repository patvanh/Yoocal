/**
 * SiteNav — the designed nav from your HTML pages.
 * Purple/amber theme, fixed top, backdrop-blur.
 *
 * Props:
 *   activeKey  — which link should be highlighted ("about" | "weekend" | "venues" | "business" | null)
 *   cityKey    — which city context, controls which links appear and where they point
 *                "parkcity" → shows "About Park City / This Weekend / Venues"
 *                "elkhartlake" → shows "About Elkhart Lake / This Weekend / Venues"
 *                undefined → shows only "About" (no city-specific links)
 */

type CityKey = "parkcity" | "elkhartlake" | "heber" | "jackson" | "greenlake";
type ActiveKey = "about" | "weekend" | "free" | "concerts" | "month" | "venues" | "business" | null;

export default function SiteNav({
  activeKey = null,
  cityKey,
}: {
  activeKey?: ActiveKey;
  cityKey?: CityKey;
}) {
  // Build the About link/label based on context
  const aboutHref =
    cityKey === "parkcity"
      ? "/about/park-city"
      : cityKey === "elkhartlake"
        ? "/about/elkhart-lake"
        : cityKey === "heber"
          ? "/about/heber"
          : cityKey === "greenlake"
            ? "/about/green-lake"
            : "/about";
  const aboutLabel =
    cityKey === "parkcity"
      ? "About Park City"
      : cityKey === "elkhartlake"
        ? "About Elkhart Lake"
        : cityKey === "heber"
          ? "About Heber"
          : cityKey === "greenlake"
            ? "About Green Lake"
            : "About";

  const KEY_TO_SLUG: Record<string,string> = {parkcity:"park-city",elkhartlake:"elkhart-lake",heber:"heber",jackson:"jackson-hole",greenlake:"green-lake"};
  const weekendHref = cityKey ? `/${KEY_TO_SLUG[cityKey] || "park-city"}/this-weekend` : "/this-weekend";
  const freeHref = cityKey ? `/${KEY_TO_SLUG[cityKey] || "park-city"}/free-events` : "/park-city/free-events";
  const concertsHref = cityKey ? `/${KEY_TO_SLUG[cityKey] || "park-city"}/concerts` : "/park-city/concerts";
  const monthHref = cityKey ? `/${KEY_TO_SLUG[cityKey] || "park-city"}/this-month` : "/park-city/this-month";
  const venuesHref = cityKey ? `/venues?city=${cityKey}` : "/venues";

  // Only show city-specific This Weekend / Venues links when we're in a city context
  const showCityLinks = !!cityKey;

  return (
    <>
      <nav className="yc-nav">
        <a href="/" className="yc-nav-logo">
          <span className="yc-nav-dot" /> yoocal
        </a>
        <div className="yc-nav-links">
          <a
            href={aboutHref}
            className={activeKey === "about" ? "active" : ""}
          >
            {aboutLabel}
          </a>
          {showCityLinks && (
            <>
              <a
                href={weekendHref}
                className={activeKey === "weekend" ? "active" : ""}
              >
                This Weekend
              </a>
              <a
                href={concertsHref}
                className={activeKey === "concerts" ? "active" : ""}
              >
                Concerts
              </a>
              <a
                href={freeHref}
                className={activeKey === "free" ? "active" : ""}
              >
                Free Events
              </a>
              <a
                href={monthHref}
                className={activeKey === "month" ? "active" : ""}
              >
                This Month
              </a>
              <a
                href={venuesHref}
                className={activeKey === "venues" ? "active" : ""}
              >
                Venues
              </a>
            </>
          )}
          <a href="/submit" className="yc-nav-secondary">Submit event</a>
          <a href="/#business">For businesses</a>
          <a
            href="https://forms.groupmail.info/subscribe/yoocal"
            target="_blank"
            rel="noopener noreferrer"
            className="yc-nav-cta"
          >
            Get notified
          </a>
        </div>
      </nav>

      <style>{`
        :root {
          --purple: #534AB7;
          --purple-light: #7B74D4;
          --purple-pale: #f0eeff;
          --amber: #EF9F27;
          --dark: #1a1830;
          --text: #1e1b3a;
          --muted: #6B7280;
          --border: rgba(83,74,183,0.12);
          --bg: #faf9ff;
        }
        .yc-nav {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          z-index: 100;
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 0 40px;
          height: 64px;
          background: rgba(250,249,255,0.85);
          backdrop-filter: blur(12px);
          -webkit-backdrop-filter: blur(12px);
          border-bottom: 1px solid var(--border);
        }
        .yc-nav-logo {
          display: flex;
          align-items: center;
          gap: 8px;
          font-family: 'DM Serif Display', serif;
          font-size: 24px;
          color: var(--purple);
          text-decoration: none;
        }
        .yc-nav-dot {
          width: 8px;
          height: 8px;
          background: var(--amber);
          border-radius: 50%;
          display: inline-block;
        }
        .yc-nav-links {
          display: flex;
          align-items: center;
          gap: 32px;
        }
        .yc-nav-links a {
          font-size: 14px;
          color: var(--muted);
          text-decoration: none;
          font-weight: 500;
          transition: color 0.2s;
        }
        .yc-nav-links a:hover,
        .yc-nav-links a.active {
          color: var(--purple);
        }
        .yc-nav-links a.yc-nav-secondary {
          background: transparent;
          border: 1.5px solid var(--purple);
          color: var(--purple) !important;
          padding: 7px 16px;
          border-radius: 100px;
          font-size: 13px;
          font-weight: 600;
        }
        .yc-nav-links a.yc-nav-secondary:hover {
          background: var(--purple-pale);
        }
        .yc-nav-links a.yc-nav-cta {
          background: var(--purple);
          color: white !important;
          padding: 8px 20px;
          border-radius: 100px;
          font-size: 13px;
          font-weight: 600;
        }
        .yc-nav-links a.yc-nav-cta:hover {
          background: var(--purple-light);
        }
        @media (max-width: 768px) {
          .yc-nav { padding: 0 20px; }
          .yc-nav-links a:not(.yc-nav-cta):not(.yc-nav-secondary) { display: none; }
        }
      `}</style>
    </>
  );
}
