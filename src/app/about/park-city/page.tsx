import type { Metadata } from "next";
import SiteNav from "@/components/SiteNav";
import SiteFooter from "@/components/SiteFooter";

export const metadata: Metadata = {
  title: "About Park City, Utah — Yoocal",
  description:
    "Everything you need to know about Park City, Utah. Events, things to do, neighborhoods, best times to visit, and local tips from Yoocal.",
  alternates: { canonical: "https://www.yoocal.com/about/park-city" },
  openGraph: {
    title: "About Park City, Utah — Yoocal",
    description:
      "Things to do in Park City, neighborhoods, seasons, getting here, and local tips.",
    url: "https://www.yoocal.com/about/park-city",
    type: "website",
  },
};

export default function AboutParkCityPage() {
  return (
    <>
      <SiteNav activeKey="about" cityKey="parkcity" />

      <div className="hero">
        <div className="hero-content">
          <div className="hero-place-title">Park City, Utah</div>
          <h1>
            The mountain town that <em>never</em> stops.
          </h1>
          <p>
            7,000 feet above sea level. World-class skiing, legendary Main
            Street, and a year-round events calendar that rivals cities ten
            times its size.
          </p>
        </div>
      </div>

      <div className="content">
        <div className="intro">
          <div className="intro-text">
            <h2>Welcome to Park City</h2>
            <p>
              Nestled in the Wasatch Mountains just 30 minutes from Salt Lake
              City, Park City is one of America&apos;s most celebrated resort
              towns. With a permanent population of around 8,500, it punches
              well above its weight — hosting the Sundance Film Festival,
              two world-class ski resorts, and a historic Main Street lined
              with galleries, restaurants, and live music venues.
            </p>
            <p>
              Whether you&apos;re a local looking for what&apos;s happening
              this weekend or a visitor planning your trip, Yoocal
              aggregates every event in Park City into one clean,
              daily-updated calendar.
            </p>
          </div>
          <div className="intro-stats">
            <div className="stat-card">
              <span className="num">
                7,000<small style={{ fontSize: 16 }}>ft</small>
              </span>
              <span className="label">Elevation</span>
            </div>
            <div className="stat-card">
              <span className="num">300+</span>
              <span className="label">Days of sunshine/year</span>
            </div>
            <div className="stat-card">
              <span className="num">8,500</span>
              <span className="label">Residents</span>
            </div>
            <div className="stat-card">
              <span className="num">~30 min</span>
              <span className="label">From SLC Airport</span>
            </div>
          </div>
        </div>

        <div className="section">
          <div className="section-label">Explore</div>
          <h2>Things to do in Park City</h2>
          <p className="subtitle">
            From world-class skiing to summer festivals — there&apos;s
            always something happening.
          </p>
          <div className="grid-3">
            <div className="card">
              <div className="card-accent" aria-hidden="true"></div>
              <h3>Skiing & Snowboarding</h3>
              <p>
                Home to Deer Valley Resort and Park City Mountain — two of
                the best ski resorts in North America with over 330 trails
                between them.
              </p>
            </div>
            <div className="card">
              <div className="card-accent" aria-hidden="true"></div>
              <h3>Live Music & Arts</h3>
              <p>
                The Egyptian Theatre, Spur Bar and Grill, and Eccles Center
                host world-class performers year-round. Sundance Film
                Festival draws Hollywood every January.
              </p>
            </div>
            <div className="card">
              <div className="card-accent" aria-hidden="true"></div>
              <h3>Hiking & Biking</h3>
              <p>
                Over 400 miles of trails accessible directly from town. The
                Rail Trail, Round Valley, and Mid-Mountain Trail are local
                favorites for all skill levels.
              </p>
            </div>
            <div className="card">
              <div className="card-accent" aria-hidden="true"></div>
              <h3>Dining & Drinks</h3>
              <p>
                High West Distillery, Handle, Riverhorse, No Name Saloon —
                Park City&apos;s dining scene competes with any major city.
                Farm-to-table meets mountain casual.
              </p>
            </div>
            <div className="card">
              <div className="card-accent" aria-hidden="true"></div>
              <h3>Festivals & Events</h3>
              <p>
                Park Silly Sunday Market runs every Sunday in summer.
                Kimball Arts Festival, Savor the Summit, and dozens of races
                and outdoor events fill the calendar year-round.
              </p>
            </div>
            <div className="card">
              <div className="card-accent" aria-hidden="true"></div>
              <h3>Shopping & Galleries</h3>
              <p>
                Historic Main Street is lined with independent boutiques,
                art galleries, and local shops. Kimball Arts Center anchors
                the arts district year-round.
              </p>
            </div>
          </div>
        </div>

        <div className="section">
          <div className="section-label">Neighborhoods</div>
          <h2>Park City neighborhoods</h2>
          <p className="subtitle">
            Each part of town has its own character and vibe.
          </p>
          {[
            {
              num: "01",
              title: "Old Town & Historic Main Street",
              body:
                "The heart of Park City. Victorian-era buildings house restaurants, bars, galleries, and the Egyptian Theatre. Park Silly Sunday Market takes over Main Street every summer Sunday.",
            },
            {
              num: "02",
              title: "Deer Valley",
              body:
                "The luxury ski resort enclave south of town. Home to Stein Eriksen Lodge, world-class ski terrain, and the Deer Valley Music Festival each summer.",
            },
            {
              num: "03",
              title: "Kimball Junction",
              body:
                "The gateway to Park City off I-80. Home to the Swaner EcoCenter, Outlets at Park City, and most of the big-box retail. Great access to trails.",
            },
            {
              num: "04",
              title: "Prospector",
              body:
                "Local neighborhood between Main Street and Kimball Junction. Home to the Park City Ice Arena, local restaurants, and the Park City Film Series cinema.",
            },
            {
              num: "05",
              title: "Snyderville Basin",
              body:
                "The broader valley stretching west toward Salt Lake. Includes Jeremy Ranch, Pinebrook, and Silver Springs. More residential, excellent trail access.",
            },
          ].map((n) => (
            <div key={n.num} className="neighborhood">
              <div className="neighborhood-num">{n.num}</div>
              <div>
                <h3>{n.title}</h3>
                <p>{n.body}</p>
              </div>
            </div>
          ))}
        </div>

        <div className="section">
          <div className="section-label">When to go</div>
          <h2>Best times to visit Park City</h2>
          <p className="subtitle">
            Park City is a true four-season destination.
          </p>
          <div className="season-grid">
            <div className="season">
              <div className="season-accent" aria-hidden="true"></div>
              <h3>Winter (Dec–Mar)</h3>
              <p>
                Peak ski season. Expect snow, crowds on weekends, and some of
                the best powder in the US. Sundance Film Festival runs late
                January.
              </p>
            </div>
            <div className="season">
              <div className="season-accent" aria-hidden="true"></div>
              <h3>Spring (Apr–May)</h3>
              <p>
                Shoulder season — fewer crowds, lower prices. Trails start
                opening. Great for a quieter visit with restaurants fully
                open.
              </p>
            </div>
            <div className="season">
              <div className="season-accent" aria-hidden="true"></div>
              <h3>Summer (Jun–Sep)</h3>
              <p>
                Peak festival season. Park Silly Sunday Market, outdoor
                concerts, hiking, biking. Warm days, cool nights. Book
                accommodation early.
              </p>
            </div>
            <div className="season">
              <div className="season-accent" aria-hidden="true"></div>
              <h3>Fall (Oct–Nov)</h3>
              <p>
                Stunning fall foliage. Quietest season — great deals on
                accommodation. Trails still open, resorts preparing for ski
                season.
              </p>
            </div>
          </div>
        </div>

        <div className="section">
          <div className="section-label">Getting here</div>
          <h2>Getting to Park City</h2>
          <p className="subtitle">
            Easier to reach than most mountain towns.
          </p>
          <div className="grid-2">
            <div className="card">
              <div className="card-accent" aria-hidden="true"></div>
              <h3>By Air</h3>
              <p>
                Salt Lake City International Airport (SLC) is just 35 miles
                away — about 30–45 minutes by car. Direct flights from most
                major US cities.
              </p>
            </div>
            <div className="card">
              <div className="card-accent" aria-hidden="true"></div>
              <h3>By Car</h3>
              <p>
                Take I-80 East from Salt Lake City to exit 145. The drive
                takes about 30 minutes in normal conditions. US-40 connects
                to Heber Valley.
              </p>
            </div>
            <div className="card">
              <div className="card-accent" aria-hidden="true"></div>
              <h3>By Shuttle</h3>
              <p>
                Several companies offer shared shuttle service from SLC
                Airport to Park City. Rates typically run $40–60 per person
                each way.
              </p>
            </div>
            <div className="card">
              <div className="card-accent" aria-hidden="true"></div>
              <h3>Getting Around</h3>
              <p>
                Free bus service (PC Transit) runs throughout town. Historic
                Main Street is very walkable. Many hotels offer
                complimentary ski resort shuttles.
              </p>
            </div>
          </div>
        </div>

        <div className="cta-banner">
          <h2>See what&apos;s happening this week</h2>
          <p>
            Yoocal aggregates every Park City event — concerts, races,
            festivals, classes, and more — updated daily.
          </p>
          <a href="/park-city" className="cta-btn">
            Browse the calendar →
          </a>
        </div>
      </div>

      <SiteFooter cityLabel="Park City, Utah" />

      <style>{`
        body { font-family: 'DM Sans', sans-serif; background: var(--bg); color: var(--text); overflow-x: hidden; }

        .hero {
          background: var(--dark);
          padding: 120px 80px 80px;
          position: relative; overflow: hidden;
        }
        .hero::before { content: ""; position: absolute; inset: 0; background: url(/hero.jpg) center 40% / cover no-repeat; opacity: 0.25; }
        .hero::after { content: ""; position: absolute; inset: 0; background: linear-gradient(to bottom, rgba(26,24,48,0.6) 0%, rgba(26,24,48,0.4) 50%, rgba(26,24,48,0.8) 100%); }
        .hero-content { position: relative; z-index: 2; max-width: 760px; margin: 0 auto; text-align: center; }
        .hero-place-title {
          font-family: 'DM Serif Display', serif;
          color: var(--purple-light);
          font-size: clamp(48px, 7vw, 80px);
          font-weight: 400; line-height: 1.05;
          margin-bottom: 20px; display: block;
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
          font-size: 32px; margin-bottom: 8px;
        }
        .section .subtitle { font-size: 16px; color: var(--muted); margin-bottom: 32px; }

        .grid-3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }
        .grid-2 { display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; }

        .card {
          background: white; border: 1px solid var(--border);
          border-radius: 16px; padding: 28px; transition: all 0.2s;
        }
        .card:hover {
          border-color: var(--purple); transform: translateY(-2px);
          box-shadow: 0 8px 24px rgba(83,74,183,0.08);
        }
        .card-icon { font-size: 28px; margin-bottom: 12px; }
        .card h3 { font-size: 16px; font-weight: 600; margin-bottom: 8px; }
        .card p { font-size: 14px; color: var(--muted); line-height: 1.7; }

        .neighborhood {
          display: grid; grid-template-columns: auto 1fr;
          gap: 20px; align-items: start;
          padding: 24px; border: 1px solid var(--border);
          border-radius: 16px; margin-bottom: 12px;
          background: white; transition: all 0.2s;
        }
        .neighborhood:hover { border-color: var(--purple); }
        .neighborhood-num {
          font-family: 'DM Serif Display', serif;
          font-size: 40px; color: var(--purple); opacity: 0.2; line-height: 1;
        }
        .neighborhood h3 { font-size: 16px; font-weight: 600; margin-bottom: 6px; }
        .neighborhood p { font-size: 14px; color: var(--muted); line-height: 1.7; }

        .season-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
        .season {
          background: white; border: 1px solid var(--border);
          border-radius: 16px; padding: 24px; text-align: center;
        }
        .season-accent { width: 40px; height: 3px; background: var(--purple); margin-bottom: 12px; }
        .season h3 { font-size: 14px; font-weight: 600; margin-bottom: 6px; }
        .season p { font-size: 13px; color: var(--muted); line-height: 1.6; }

        .cta-banner {
          background: var(--dark); border-radius: 24px;
          padding: 60px; text-align: center; margin-top: 80px;
        }
        .cta-banner h2 {
          font-family: 'DM Serif Display', serif;
          font-size: 36px; color: white; margin-bottom: 16px;
        }
        .cta-banner p { color: rgba(255,255,255,0.5); font-size: 16px; margin-bottom: 32px; }
        .cta-btn {
          display: inline-block; background: var(--purple);
          color: white; padding: 14px 32px;
          border-radius: 100px; font-size: 15px; font-weight: 600;
          text-decoration: none;
        }
        .cta-btn:hover { background: var(--purple-light); }

        @media (max-width: 768px) {
          .hero { padding: 100px 24px 60px; }
          .content { padding: 48px 24px; }
          .intro { grid-template-columns: 1fr; gap: 40px; }
          .grid-3, .season-grid { grid-template-columns: 1fr 1fr; }
          .grid-2 { grid-template-columns: 1fr; }
        }
      `}</style>
    </>
  );
}
