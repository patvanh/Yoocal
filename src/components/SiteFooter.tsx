/**
 * SiteFooter — designed footer with a site-wide internal link mesh
 * (cities + intent hubs + key pages) for discovery/SEO, in the dark hero style.
 */
const CITIES: Array<{ slug: string; name: string }> = [
  { slug: "park-city", name: "Park City" },
  { slug: "heber", name: "Heber Valley" },
  { slug: "jackson-hole", name: "Jackson Hole" },
  { slug: "elkhart-lake", name: "Elkhart Lake" },
];
const HUBS: Array<{ seg: string; label: string }> = [
  { seg: "this-weekend", label: "This weekend" },
  { seg: "concerts", label: "Concerts" },
  { seg: "free-events", label: "Free events" },
  { seg: "this-month", label: "This month" },
];

export default function SiteFooter({ cityLabel }: { cityLabel?: string }) {
  return (
    <>
      <footer className="yc-footer">
        <div className="yc-footer-nav">
          <div className="yc-foot-col">
            <span className="yc-foot-h">Cities</span>
            {CITIES.map((c) => (<a key={c.slug} href={`/${c.slug}`}>{c.name}</a>))}
          </div>
          {HUBS.map((h) => (
            <div className="yc-foot-col" key={h.seg}>
              <span className="yc-foot-h">{h.label}</span>
              {CITIES.map((c) => (<a key={c.slug} href={`/${c.slug}/${h.seg}`}>{c.name}</a>))}
            </div>
          ))}
          <div className="yc-foot-col">
            <span className="yc-foot-h">Yoocal</span>
            <a href="/about">About</a>
            <a href="/venues">Venues</a>
            <a href="/for-businesses">For businesses</a>
            <a href="/submit">Submit event</a>
          </div>
        </div>
        <div className="yc-footer-bottom">
          <span>© 2026 Yoocal{cityLabel ? ` · ${cityLabel}` : ""}</span>
          <span>hello@yoocal.com</span>
        </div>
      </footer>

      <style>{`
        .yc-footer { background: var(--dark, #1a1830); color: white; padding: 48px 80px 28px; }
        .yc-footer-nav { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 28px 24px; max-width: 1100px; margin: 0 auto 28px; }
        .yc-foot-col { display: flex; flex-direction: column; gap: 9px; }
        .yc-foot-h { font-size: 12px; font-weight: 700; letter-spacing: 0.4px; text-transform: uppercase; color: rgba(255,255,255,0.5); margin-bottom: 3px; }
        .yc-foot-col a { font-size: 14px; color: rgba(255,255,255,0.75); text-decoration: none; line-height: 1.3; }
        .yc-foot-col a:hover { color: #fff; text-decoration: underline; }
        .yc-footer-bottom {
          font-size: 13px; color: rgba(255,255,255,0.25);
          display: flex; justify-content: space-between;
          padding-top: 20px; border-top: 1px solid rgba(255,255,255,0.08);
          max-width: 1100px; margin: 0 auto;
        }
        @media (max-width: 768px) {
          .yc-footer { padding: 40px 24px 28px; }
          .yc-footer-bottom { flex-direction: column; gap: 8px; }
        }
      `}</style>
    </>
  );
}
