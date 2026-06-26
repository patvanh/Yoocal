
/**
 * HomeServer — server-rendered canonical content for the homepage.
 *
 * The interactive homepage (HomeBrand) is a client component gated behind
 * HomeRouter's loading state, so crawlers/no-JS visitors saw a 60-char
 * "Loading..." shell. This renders the real brand statement and the city
 * directory server-side: an H1 establishing what Yoocal is (also addresses the
 * brand-entity gap), a description, and the cities as real links. Separate
 * render tree from the client app — no hydration coupling.
 */


export default function HomeServer() {
  return (
    <section className="home-server" aria-label="About Yoocal and cities covered">
      <div className="home-server-inner">
        <h1 className="home-server-h1">Local events in scenic resort &amp; mountain towns</h1>
        <p className="home-server-lede">
          Yoocal is a free, daily-updated events calendar for resort and mountain communities.
          We aggregate concerts, festivals, races, food, outdoor adventures, and family events
          from local sources — venues, chambers of commerce, and public calendars — so you can
          find everything happening near you in one place. Browse a city:
        </p>
        <p className="home-server-foot">
          For each city, browse <a href="/park-city/this-weekend">this weekend</a>,{" "}
          <a href="/park-city/free-events">free events</a>, <a href="/park-city/concerts">concerts</a>,
          and more. Organizers can <a href="/submit">submit an event</a> free or{" "}
          <a href="/for-businesses">promote a listing</a>.
        </p>
      </div>

      <style>{`
        .home-server { background: #1a1830; padding: 44px 16px 48px; border-top: 1px solid rgba(255,255,255,0.06); }
        .home-server-inner { max-width: 1100px; margin: 0 auto; }
        .home-server-h1 { font-family: 'DM Sans', sans-serif; font-size: 13px; font-weight: 700; letter-spacing: 0.4px; text-transform: uppercase; line-height: 1.3; color: #b9aef5; margin: 0 0 10px; max-width: 760px; }
        .home-server-lede { font-size: 13.5px; line-height: 1.6; color: rgba(255,255,255,0.5); margin: 0 0 20px; max-width: 720px; }
        .home-server-cities { list-style: none; padding: 0; margin: 0 0 20px; display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 8px; }
        .home-server-city a { display: flex; flex-direction: column; gap: 3px; padding: 11px 14px; background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; text-decoration: none; transition: background 0.15s, border-color 0.15s; height: 100%; }
        .home-server-city a:hover { background: rgba(255,255,255,0.07); border-color: rgba(185,174,245,0.4); }
        .home-server-city-name { font-size: 13.5px; font-weight: 600; color: rgba(255,255,255,0.92); }
        .home-server-city-blurb { font-size: 12px; line-height: 1.4; color: rgba(255,255,255,0.45); }
        .home-server-foot { font-size: 13px; line-height: 1.6; color: rgba(255,255,255,0.5); max-width: 760px; margin: 0; }
        .home-server-foot a { color: #b9aef5; text-decoration: none; border-bottom: 1px solid rgba(185,174,245,0.3); }
        .home-server-foot a:hover { border-bottom-color: #b9aef5; }
        @media (max-width: 640px) { .home-server-h1 { font-size: 12px; } }
      `}</style>
    </section>
  )
}
