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

import CityPicker from "@/components/CityPicker";
import RadiusPicker from "@/components/RadiusPicker";
import NavMenu from "@/components/NavMenu";

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
            : cityKey === "jackson"
              ? "/about/jackson-hole"
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
            : cityKey === "jackson"
              ? "About Jackson Hole"
              : "About";

  const KEY_TO_SLUG: Record<string,string> = {parkcity:"park-city",elkhartlake:"elkhart-lake",heber:"heber",jackson:"jackson-hole",greenlake:"green-lake"};
  const calendarHref = cityKey ? `/${KEY_TO_SLUG[cityKey] || "park-city"}` : "/";
  const weekendHref = cityKey ? `/${KEY_TO_SLUG[cityKey] || "park-city"}/this-weekend` : "/this-weekend";
  const freeHref = cityKey ? `/${KEY_TO_SLUG[cityKey] || "park-city"}/free-events` : "/park-city/free-events";
  const concertsHref = cityKey ? `/${KEY_TO_SLUG[cityKey] || "park-city"}/concerts` : "/park-city/concerts";
  const monthHref = cityKey ? `/${KEY_TO_SLUG[cityKey] || "park-city"}/this-month` : "/park-city/this-month";
  const venuesHref = cityKey ? `/venues?city=${cityKey}` : "/venues";

  // Only show city-specific This Weekend / Venues links when we're in a city context
  const showCityLinks = !!cityKey;

  // Link list for the mobile hamburger menu (same hrefs/labels as the bar).
  const menuLinks: { href: string; label: string; active?: boolean; external?: boolean }[] = [
    { href: aboutHref, label: aboutLabel, active: activeKey === "about" },
    ...(showCityLinks ? [
      { href: weekendHref, label: "This Weekend", active: activeKey === "weekend" },
      { href: concertsHref, label: "Concerts", active: activeKey === "concerts" },
      { href: freeHref, label: "Free Events", active: activeKey === "free" },
      { href: monthHref, label: "This Month", active: activeKey === "month" },
      { href: venuesHref, label: "Venues", active: activeKey === "venues" },
    ] : []),
    { href: "/#business", label: "For businesses" },
  ];

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
          <a href="/#business">For businesses</a>
          {cityKey && <span className="yc-nav-pickers" style={{ display: 'flex', alignItems: 'center', marginLeft: 'auto' }}><CityPicker cityKey={cityKey} /></span>}
          {cityKey && <span className="yc-nav-pickers" style={{ display: 'flex', alignItems: 'center' }}><a href={calendarHref} className="yc-nav-cta">Calendar</a></span>}
          <a
            href="https://forms.groupmail.info/subscribe/yoocal"
            target="_blank"
            rel="noopener noreferrer"
            className="yc-nav-secondary"
          >
            Get notified
          </a>
        </div>
        {/* Tight right-cluster: city + radius + Submit, grouped with a small
            gap on the right (matches the mockup). Sits outside yc-nav-links so
            its wide 32px gap doesn't spread these apart. */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginLeft: 16 }}>
          <a href="/submit" className="yc-nav-secondary">Submit event</a>
        </div>
        <div style={{ marginLeft: 12 }}><NavMenu links={menuLinks} /></div>
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
          z-index: 1000;
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
          gap: 28px;
          flex: 1;
          margin-left: 40px;
        }
        .yc-nav-links a {
          font-size: 14px;
          color: var(--muted);
          text-decoration: none;
          font-weight: 500;
          transition: color 0.2s;
          white-space: nowrap;
        }
        .yc-nav-links a:hover,
        .yc-nav-links a.active {
          color: var(--purple);
        }
        a.yc-nav-secondary {
          background: transparent;
          border: 1.5px solid var(--purple);
          color: var(--purple) !important;
          padding: 7px 14px;
          border-radius: 100px;
          font-size: 12px;
          font-weight: 600;
          white-space: nowrap;
          text-decoration: none;
        }
        a.yc-nav-secondary:hover {
          background: var(--purple-pale);
        }
        .yc-nav-links a.yc-nav-cta {
          background: var(--purple);
          color: white !important;
          padding: 7px 14px;
          border-radius: 100px;
          font-size: 12px;
          font-weight: 600;
          white-space: nowrap;
        }
        .yc-nav-links a.yc-nav-cta:hover {
          background: var(--purple-light);
        }
        /* City picker lives in the header at all widths. */
        .yc-nav-pickers { display: flex !important; }
        /* Hamburger: hidden on desktop (full nav shows), revealed below breakpoint. */
        .yc-hamburger { display: none; }
        @media (max-width: 1300px) {
          .yc-nav { padding: 0 14px; }
          /* Below breakpoint: hide the nav links into the hamburger, but KEEP
             both CTA buttons (Get notified + Submit) and the city pill visible. */
          .yc-nav-links a:not(.yc-nav-secondary):not(.yc-nav-cta) { display: none; }
          .yc-hamburger { display: block; }
        }
      `}</style>
    </>
  );
}
