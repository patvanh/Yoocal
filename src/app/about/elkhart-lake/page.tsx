import type { Metadata } from "next";
import SiteNav from "@/components/SiteNav";
import SiteFooter from "@/components/SiteFooter";

export const metadata: Metadata = {
  title: "About Elkhart Lake, Wisconsin — Yoocal",
  description:
    "Everything you need to know about Elkhart Lake, Wisconsin. Road America racing, lakeside dining, local events, best times to visit, and insider tips from Yoocal.",
  alternates: { canonical: "https://www.yoocal.com/about/elkhart-lake" },
  openGraph: {
    title: "About Elkhart Lake, Wisconsin — Yoocal",
    description:
      "Road America racing, lakeside resorts, village life and what to know before you visit.",
    url: "https://www.yoocal.com/about/elkhart-lake",
    type: "website",
  },
};

const RACES_2026 = [
  { dates: "May 15–17", title: "Spring Vintage Weekend with SVRA", desc: "Classic racecars from the '50s–'70s — Lotus, Alfa Romeo, Jaguar, Porsche, Corvette", major: false },
  { dates: "May 29–31", title: "MotoAmerica Superbikes & Vintage MotoFest", desc: "Championship motorcycle racing plus a family-friendly vintage motorcycle festival", major: false },
  { dates: "Jun 5–7", title: "WeatherTech SCCA June Sprints", desc: "Road America's longest-running event — the best of grassroots road racing", major: false },
  { dates: "Jun 18–21", title: "XPEL INDYCAR Grand Prix", desc: "North America's premier open-wheel series on one of the world's most majestic courses", major: true },
  { dates: "Jul 16–19", title: "WeatherTech Vintage Weekend with Brian Redman", desc: "400+ historic racecars, Dan Gurney Racing Eagles reunion, 60th anniversary Trans Am tribute", major: true },
  { dates: "Jul 30–Aug 2", title: "Motul SportsCar Endurance Grand Prix — IMSA", desc: "Six-hour endurance race featuring Ferrari, Mercedes, Chevrolet, Aston Martin and more", major: true },
  { dates: "Aug 28–30", title: "GT World Challenge America", desc: "All-sportscar weekend featuring GT racing's top international teams", major: false },
  { dates: "Sep 18–20", title: "Art on Wheels Weekend with VSCDA", desc: "300+ vintage and historic race cars spanning 11 racing classes", major: false },
  { dates: "Oct 1–4", title: "SCCA National Championship Runoffs", desc: "The pinnacle of US amateur road racing — top SCCA racers battle for national titles", major: false },
];

const VILLAGE_CARDS = [
  { icon: "🍺", title: "Siebkens Resort", body: "The soul of Elkhart Lake since 1916. Lakeside tavern, live music most weekends, and a lively crowd that includes racing legends, locals, and everyone in between. The Stop-Inn Tavern opens in April." },
  { icon: "🏨", title: "Osthoff Resort", body: "A premier lakefront resort with a full spa, cooking classes, fine dining, and year-round events. Perfect for a romantic getaway or a pre-race splurge. Overlooks the lake with stunning views." },
  { icon: "🌾", title: "Farmers & Artisans Market", body: "Every Saturday morning in the Village Square from May through October. About 50 vendors with fresh vegetables, flowers, cheese, local arts, and specialty products. A true community tradition." },
  { icon: "🚣", title: "Elkhart Lake", body: "The glacier-carved lake the village is named for. Crystal clear water perfect for swimming, kayaking, paddleboarding, and fishing. Several public access points and rentals available in summer." },
  { icon: "🍽️", title: "The Paddock Club", body: "A favorite gathering spot in the village for food, drinks, and good company. Especially lively during race weekends when drivers, crew members, and fans all end up at the same tables." },
  { icon: "🛍️", title: "Shop & Sip", body: "The annual Shop & Sip event brings together Elkhart Lake's downtown shops and restaurants for a day of shopping, tastings, and community fun. A favorite for locals and visitors alike." },
];

const TIPS = [
  { icon: "🏁", title: "Book early for race weekends", body: "IndyCar (June), IMSA (July/August), and Vintage Weekend (July) fill up months in advance. Hotels within 30 miles sell out fast. Book as early as possible — seriously." },
  { icon: "🌤️", title: "Best weather: June–August", body: "Wisconsin summers are warm and beautiful with low humidity compared to much of the midwest. Evenings cool down nicely — perfect for outdoor dining and lakeside drinks." },
  { icon: "🚗", title: "You'll need a car", body: "Elkhart Lake is a 90-minute drive from Milwaukee and 2.5 hours from Chicago. There's no public transit — a car is essential. Road America is just 5 minutes from the village center." },
  { icon: "🎟️", title: "General admission is great", body: "Unlike many venues, Road America's general admission tickets let you walk the entire track perimeter and get incredibly close to the action. You don't need the expensive seats to have an amazing time." },
  { icon: "🍔", title: "The food scene is real", body: "Don't underestimate Elkhart Lake's restaurants. The Osthoff's Lola's on the Lake, Siebkens, and several village spots serve genuinely excellent food. Make reservations for race weekends." },
  { icon: "📍", title: "Stay in the village if you can", body: "Staying in Elkhart Lake itself — rather than in Plymouth or Sheboygan — puts you in the center of the action. Walking to Siebkens after a race day is one of the great pleasures of visiting." },
];

export default function AboutElkhartLakePage() {
  return (
    <>
      <SiteNav activeKey="about" cityKey="elkhartlake" />

      <div className="hero">
        <div className="hero-inner">
          <div className="hero-content-wrap"><div className="hero-content">
            <div className="hero-eyebrow">🏁 Elkhart Lake, Wisconsin</div>
            <h1>
              America&apos;s <em>hidden gem</em> of speed & serenity.
            </h1>
            <p>
              A charming lakeside village of 1,000 people that draws tens of
              thousands every summer for world-class racing, live music on
              the water, and a pace of life that feels like a different era.
            </p>
          </div></div><div className="hero-image"><img src="/roadamericaradical.webp" alt="Racing at Road America, Elkhart Lake Wisconsin" /></div></div></div>

      <div className="content">
        <div className="intro">
          <div className="intro-text">
            <h2>Small town. Big personality.</h2>
            <p>
              Elkhart Lake sits on the shores of its namesake glacier-carved
              lake in Sheboygan County, Wisconsin. What it lacks in size it
              more than makes up for in character — and in the roar of
              engines from Road America, one of the greatest road courses in
              the world.
            </p>
            <p>
              From the legendary Siebkens Resort (open since 1916) to the
              Osthoff&apos;s lakefront spa, from the Saturday farmers market
              to the thundering IndyCar weekend, Elkhart Lake offers a rare
              combination: genuine small-town warmth alongside world-class
              events.
            </p>
          </div>
          <div className="intro-stats">
            <div className="stat-card">
              <span className="num">4.0</span>
              <div className="label">Miles of Road America track</div>
            </div>
            <div className="stat-card">
              <span className="num">50+</span>
              <div className="label">Days of racing per year</div>
            </div>
            <div className="stat-card">
              <span className="num">1,000</span>
              <div className="label">Village population</div>
            </div>
            <div className="stat-card">
              <span className="num">1916</span>
              <div className="label">Siebkens Resort founded</div>
            </div>
          </div>
        </div>

        <div className="section">
          <div className="section-label">Road America</div>
          <h2>
            America&apos;s <em>National Park of Speed</em>
          </h2>
          <p>
            Road America is the crown jewel — a 4-mile, 14-turn natural road
            course carved through 640 acres of rolling Wisconsin
            countryside. Built in 1955, it consistently ranks among the
            world&apos;s greatest race tracks. The racing calendar runs from
            May through October with something for every type of fan.
          </p>

          <div className="race-schedule">
            <h3>2026 Race Season</h3>
            <div className="sub">
              All events at Road America · N7390 US-12, Elkhart Lake, WI
            </div>
            {RACES_2026.map((r) => (
              <div key={r.title} className="race-item">
                <div className="race-dates">{r.dates}</div>
                <div className="race-info">
                  <h4>{r.title}</h4>
                  <p>{r.desc}</p>
                </div>
                {r.major && <div className="race-badge major">Major</div>}
              </div>
            ))}
          </div>
        </div>

        <div className="section">
          <div className="section-label">Beyond the track</div>
          <h2>
            The village <em>life</em>
          </h2>
          <p>
            Race weekend or not, Elkhart Lake has a rhythm all its own. The
            village square, the lake, the Saturday market, the music at
            Siebkens — it all adds up to something genuinely special.
          </p>

          <div className="cards-grid">
            {VILLAGE_CARDS.map((c) => (
              <div key={c.title} className="card">
                <div className="card-icon">{c.icon}</div>
                <h3>{c.title}</h3>
                <p>{c.body}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="section">
          <div className="section-label">Plan your visit</div>
          <h2>
            When to go & <em>what to know</em>
          </h2>
          <p>
            Elkhart Lake is a summer destination at heart, with the racing
            season and village events running May through October.
          </p>

          <div className="tips-grid">
            {TIPS.map((t) => (
              <div key={t.title} className="tip">
                <div className="tip-icon">{t.icon}</div>
                <h4>{t.title}</h4>
                <p>{t.body}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="cta-banner">
          <h2>
            See what&apos;s happening <em>this weekend.</em>
          </h2>
          <p>Live events, races, music, and more — all in one place.</p>
          <a href="/?city=elkhartlake" className="cta-btn">
            Browse Elkhart Lake events →
          </a>
        </div>
      </div>

      <SiteFooter cityLabel="Elkhart Lake, Wisconsin" />

      <style>{`
        body { font-family: 'DM Sans', sans-serif; background: var(--bg); color: var(--text); overflow-x: hidden; }

        .hero {
          background: var(--dark);
          padding: 120px 80px 80px;
          position: relative; overflow: hidden;
        }
        .hero::before {
          content: ''; position: absolute; inset: 0;
          background: linear-gradient(135deg, #0a1628 0%, #1a2840 50%, #0d1f35 100%);
        }
        .hero::after {
          content: ''; position: absolute; inset: 0;
          background: radial-gradient(ellipse 80% 60% at 20% 80%, rgba(83,74,183,0.25) 0%, transparent 70%);
        }
        .hero-inner { position: relative; z-index: 2; max-width: 1200px; margin: 0 auto; display: flex; align-items: center; gap: 60px; }
        .hero-content { max-width: 720px; }
        .hero-image { flex: 1; min-width: 0; border-radius: 16px; overflow: hidden; box-shadow: 0 24px 64px rgba(0,0,0,0.5); }
        .hero-image img { width: 100%; height: 380px; object-fit: cover; display: block; }
        .hero-eyebrow {
          display: inline-flex; align-items: center; gap: 8px;
          background: rgba(255,255,255,0.1); color: rgba(255,255,255,0.9);
          font-size: 12px; font-weight: 600;
          padding: 5px 14px; border-radius: 100px;
          margin-bottom: 24px; letter-spacing: 0.5px;
          border: 1px solid rgba(255,255,255,0.15);
        }
        .hero h1 {
          font-family: 'DM Serif Display', serif;
          font-size: clamp(40px, 6vw, 72px);
          color: white; line-height: 1.05; margin-bottom: 20px;
        }
        .hero h1 em { font-style: italic; color: var(--purple-light); }
        .hero p {
          font-size: 18px; color: rgba(255,255,255,0.6);
          line-height: 1.7; font-weight: 300; max-width: 560px;
        }

        .content { max-width: 1100px; margin: 0 auto; padding: 80px 40px; }

        .intro {
          display: grid; grid-template-columns: 1fr 1fr;
          gap: 80px; align-items: start; margin-bottom: 80px;
        }
        .intro-text h2 {
          font-family: 'DM Serif Display', serif;
          font-size: 36px; margin-bottom: 20px;
        }
        .intro-text p { font-size: 16px; color: var(--muted); line-height: 1.8; margin-bottom: 16px; }
        .intro-stats { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
        .stat-card {
          background: var(--purple-pale); border-radius: 16px;
          padding: 24px; text-align: center;
        }
        .stat-card .num {
          font-family: 'DM Serif Display', serif;
          font-size: 32px; color: var(--purple); display: block;
        }
        .stat-card .label { font-size: 12px; color: var(--muted); margin-top: 4px; }

        .section { margin-bottom: 72px; }
        .section-label {
          font-size: 12px; font-weight: 700; text-transform: uppercase;
          letter-spacing: 1px; color: var(--amber);
          margin-bottom: 8px; display: flex; align-items: center; gap: 8px;
        }
        .section-label::before {
          content: ''; width: 24px; height: 2px;
          background: var(--purple-light); display: inline-block;
        }
        .section h2 {
          font-family: 'DM Serif Display', serif;
          font-size: clamp(28px, 4vw, 40px);
          margin-bottom: 16px; line-height: 1.2;
        }
        .section h2 em { font-style: italic; color: var(--purple); }
        .section p { font-size: 16px; color: var(--muted); line-height: 1.8; margin-bottom: 16px; max-width: 700px; }

        .cards-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
          gap: 20px; margin-top: 28px;
        }
        .card {
          background: white; border: 1px solid var(--border);
          border-radius: 20px; padding: 28px; transition: all 0.2s;
        }
        .card:hover {
          border-color: var(--purple); transform: translateY(-3px);
          box-shadow: 0 12px 32px rgba(83,74,183,0.08);
        }
        .card-icon { font-size: 32px; margin-bottom: 14px; }
        .card h3 { font-size: 17px; font-weight: 600; margin-bottom: 8px; }
        .card p { font-size: 14px; color: var(--muted); line-height: 1.7; }

        .race-schedule {
          background: var(--dark); border-radius: 24px;
          padding: 48px; margin-top: 28px;
        }
        .race-schedule h3 {
          font-family: 'DM Serif Display', serif;
          font-size: 28px; color: white; margin-bottom: 8px;
        }
        .race-schedule .sub {
          font-size: 14px; color: rgba(255,255,255,0.4);
          margin-bottom: 32px;
        }
        .race-item {
          display: flex; align-items: flex-start; gap: 20px;
          padding: 16px 0;
          border-bottom: 1px solid rgba(255,255,255,0.07);
        }
        .race-item:last-child { border-bottom: none; }
        .race-dates {
          font-size: 12px; font-weight: 700; color: var(--amber);
          min-width: 90px; padding-top: 2px;
          text-transform: uppercase; letter-spacing: 0.5px;
        }
        .race-info { flex: 1; min-width: 0; }
        .race-info h4 { font-size: 15px; font-weight: 600; color: white; margin-bottom: 3px; }
        .race-info p { font-size: 13px; color: rgba(255,255,255,0.4); }
        .race-badge {
          margin-left: auto; font-size: 10px; font-weight: 700;
          padding: 3px 10px; border-radius: 100px;
          background: rgba(83,74,183,0.3); color: var(--purple-light);
          white-space: nowrap; flex-shrink: 0;
        }
        .race-badge.major {
          background: rgba(239,159,39,0.2); color: var(--amber);
        }

        .tips-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; margin-top: 28px; }
        .tip {
          background: white; border: 1px solid var(--border);
          border-radius: 16px; padding: 24px;
        }
        .tip-icon { font-size: 24px; margin-bottom: 10px; }
        .tip h4 { font-size: 15px; font-weight: 600; margin-bottom: 6px; }
        .tip p { font-size: 14px; color: var(--muted); line-height: 1.7; }

        .cta-banner {
          background: var(--dark); border-radius: 24px;
          padding: 64px; text-align: center; margin-top: 80px;
        }
        .cta-banner h2 {
          font-family: 'DM Serif Display', serif;
          font-size: 40px; color: white; margin-bottom: 16px;
          line-height: 1.2;
        }
        .cta-banner h2 em { font-style: italic; color: var(--purple-light); }
        .cta-banner p { color: rgba(255,255,255,0.5); font-size: 17px; margin-bottom: 32px; }
        .cta-btn {
          display: inline-block; background: var(--purple);
          color: white; padding: 14px 32px;
          border-radius: 100px; font-size: 15px; font-weight: 600;
          text-decoration: none; transition: background 0.2s;
        }
        .cta-btn:hover { background: var(--purple-light); }

        @media (max-width: 768px) {
          .hero { padding: 100px 24px 60px; }
          .hero-inner { flex-direction: column; gap: 32px; }
          .hero-image img { height: 220px; }
          .content { padding: 48px 24px; }
          .intro { grid-template-columns: 1fr; gap: 40px; }
          .tips-grid { grid-template-columns: 1fr; }
          .race-schedule { padding: 32px 24px; }
          .cta-banner { padding: 48px 28px; }
        }
      `}</style>
    </>
  );
}
