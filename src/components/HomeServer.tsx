import { CITY_CONFIG, type CityKey } from "@/lib/events"

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

const CITIES: Array<{ slug: string; name: string; region: string; blurb: string }> = [
  { slug: "park-city", name: "Park City", region: "Utah", blurb: "Concerts, festivals, races, outdoor adventures and more." },
  { slug: "jackson-hole", name: "Jackson Hole", region: "Wyoming", blurb: "Music festivals, chamber events, and Teton County happenings." },
  { slug: "heber", name: "Heber Valley", region: "Utah", blurb: "Rodeos, fairs, train rides and small-town events across the Wasatch Back." },
  { slug: "elkhart-lake", name: "Elkhart Lake", region: "Wisconsin", blurb: "Racing, lakeside events and everything around Road America." },
  { slug: "green-lake", name: "Green Lake", region: "Wisconsin", blurb: "Golf, boating, summer concerts and small-town events on Wisconsin's deepest lake." },
]

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
        <ul className="home-server-cities">
          {CITIES.map((c) => (
            <li key={c.slug} className="home-server-city">
              <a href={`/${c.slug}`}>
                <span className="home-server-city-name">{c.name}, {c.region}</span>
                <span className="home-server-city-blurb">{c.blurb}</span>
              </a>
            </li>
          ))}
        </ul>
        <p className="home-server-foot">
          For each city, browse <a href="/park-city/this-weekend">this weekend</a>,{" "}
          <a href="/park-city/free-events">free events</a>, <a href="/park-city/concerts">concerts</a>,
          and more. Organizers can <a href="/submit">submit an event</a> free or{" "}
          <a href="/for-businesses">promote a listing</a>.
        </p>
      </div>

      <style>{`
        .home-server { background: #faf9ff; padding: 16px 16px 56px; }
        .home-server-inner { max-width: 1100px; margin: 0 auto; }
        .home-server-h1 { font-family: 'DM Serif Display', serif; font-size: 30px; line-height: 1.14; color: #1e1b3a; margin: 0 0 12px; max-width: 760px; }
        .home-server-lede { font-size: 15px; line-height: 1.65; color: #5b5676; margin: 0 0 22px; max-width: 760px; }
        .home-server-cities { list-style: none; padding: 0; margin: 0 0 22px; display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 10px; }
        .home-server-city a { display: flex; flex-direction: column; gap: 4px; padding: 14px 16px; background: #fff; border: 1px solid #ece8fa; border-radius: 12px; text-decoration: none; transition: border-color 0.15s; height: 100%; }
        .home-server-city a:hover { border-color: #b9aef5; }
        .home-server-city-name { font-size: 15px; font-weight: 700; color: #1e1b3a; }
        .home-server-city-blurb { font-size: 13px; line-height: 1.45; color: #8a85a6; }
        .home-server-foot { font-size: 14px; line-height: 1.6; color: #5b5676; max-width: 760px; }
        .home-server-foot a { color: #7b5cff; text-decoration: none; border-bottom: 1px solid rgba(123,92,255,0.3); }
        .home-server-foot a:hover { border-bottom-color: #7b5cff; }
        @media (max-width: 640px) { .home-server-h1 { font-size: 25px; } }
      `}</style>
    </section>
  )
}
