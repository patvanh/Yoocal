import type { Metadata } from "next";
import SiteNav from "@/components/SiteNav";
import SiteFooter from "@/components/SiteFooter";

export const metadata: Metadata = {
  title: "About Heber Valley, Utah — Yoocal",
  description:
    "Everything you need to know about Heber Valley, Utah. Soldier Hollow, Heber Valley Railroad, farm tours, fishing, and what's happening — 25 minutes from Park City.",
  alternates: { canonical: "https://www.yoocal.com/about/heber" },
  openGraph: {
    title: "About Heber Valley, Utah — Yoocal",
    description:
      "Soldier Hollow, Heber Valley Railroad, the dairy farms, Deer Creek Reservoir, and the small-town charm 25 minutes from Park City.",
    url: "https://www.yoocal.com/about/heber",
    type: "website",
  },
};

export default function AboutHeberPage() {
  return (
    <>
      <SiteNav activeKey="about" cityKey="heber" />

      <div className="hero">
        <div className="hero-inner-hv">
          <div className="hero-content-hv">
            <div className="hero-place-title-hv">Heber Valley, Utah</div>
            <h1>
              The valley <em>just over</em> the pass.
            </h1>
            <p>
              5,600 feet above sea level. Working dairy farms, the Heber
              Valley Railroad, Soldier Hollow Olympic venue, Deer Creek
              Reservoir, and the Utah you came west to find — 25 minutes from
              Park City.
            </p>
          </div>
          <div className="hero-image-hv"><img src="/heber.jpg" alt="Heber Valley, Utah — historic barn with Mount Timpanogos behind" /></div>
        </div>
      </div>

      <div className="content">
        <div className="intro">
          <div className="intro-text">
            <h2>Welcome to Heber Valley</h2>
            <p>
              Tucked between the Wasatch Range and the Uinta Mountains,
              Heber Valley is what Park City was before Park City became
              Park City. The valley floor is wide and green, the towns of
              Heber City and Midway are walkable and historic, and a
              farming heritage runs through every block.
            </p>
            <p>
              The 2002 Winter Olympics put Soldier Hollow on the map for
              biathlon and cross-country skiing. The Heber Valley Railroad
              has been running historic steam excursions for decades. The
              dairy farms still run daily tours. And Deer Creek Reservoir
              draws boaters, anglers, and paddleboarders every summer.
              Whether you live here or you&apos;re visiting from Park City
              for the afternoon, Yoocal pulls together everything happening
              into one daily-updated calendar.
            </p>
          </div>
          <div className="intro-stats">
            <div className="stat-card">
              <span className="num">
                5,600<small style={{ fontSize: 16 }}>ft</small>
              </span>
              <span className="label">Elevation</span>
            </div>
            <div className="stat-card">
              <span className="num">~17K</span>
              <span className="label">Heber City population</span>
            </div>
            <div className="stat-card">
              <span className="num">25 min</span>
              <span className="label">From Park City</span>
            </div>
            <div className="stat-card">
              <span className="num">2002</span>
              <span className="label">Soldier Hollow Olympics</span>
            </div>
          </div>
        </div>

        <div className="section">
          <div className="section-label">Explore</div>
          <h2>Things to do in Heber Valley</h2>
          <p className="subtitle">
            Outdoor, agricultural, and family-friendly — the valley
            specializes in slower-paced fun.
          </p>
          <div className="grid-3">
            <div className="card">
              <div className="card-accent" aria-hidden="true"></div>
              <h3>Heber Valley Railroad</h3>
              <p>
                Year-round historic train excursions through the valley.
                Dinner trains, holiday specials, and themed rides for
                kids — one of Utah&apos;s longest-running heritage
                attractions.
              </p>
            </div>
            <div className="card">
              <div className="card-accent" aria-hidden="true"></div>
              <h3>Soldier Hollow</h3>
              <p>
                2002 Olympic biathlon and cross-country venue. Tubing,
                Nordic skiing, biathlon clinics, and the famous Soldier
                Hollow Classic sheepdog championships every Labor Day.
              </p>
            </div>
            <div className="card">
              <div className="card-accent" aria-hidden="true"></div>
              <h3>Deer Creek Reservoir</h3>
              <p>
                Stunning state-park reservoir for boating, paddleboarding,
                fishing, and swimming. Calm waters and Wasatch views.
                Less crowded than Jordanelle.
              </p>
            </div>
            <div className="card">
              <div className="card-accent" aria-hidden="true"></div>
              <h3>Dairy Farm Tours</h3>
              <p>
                Working family dairies open their gates for tours, ice
                cream, and barn visits. A genuine, hands-on look at
                Utah&apos;s farm heritage that the kids love.
              </p>
            </div>
            <div className="card">
              <div className="card-accent" aria-hidden="true"></div>
              <h3>Hiking & Mountain Biking</h3>
              <p>
                The Wasatch Crest, Mill Hollow, and dozens of valley
                trails connect Heber to Park City and Midway. Less
                trafficked than the Park City side, often more scenic.
              </p>
            </div>
            <div className="card">
              <div className="card-accent" aria-hidden="true"></div>
              <h3>Midway Swiss Days & Dining</h3>
              <p>
                Historic Midway hosts Swiss Days every Labor Day weekend.
                Year-round, the town has classic American diners, the
                Midway Mercantile, and the famous Homestead Crater for
                geothermal swimming.
              </p>
            </div>
          </div>
        </div>

        <div className="section">
          <div className="section-label">Getting here</div>
          <h2>Getting to Heber Valley</h2>
          <p className="subtitle">
            Easier than you&apos;d think — and right next to Park City.
          </p>
          <div className="grid-2">
            <div className="card">
              <div className="card-accent" aria-hidden="true"></div>
              <h3>By Air</h3>
              <p>
                Salt Lake City International Airport (SLC) is about 50
                miles — roughly 50–60 minutes via I-80 East and US-40
                South. Direct from most major US cities.
              </p>
            </div>
            <div className="card">
              <div className="card-accent" aria-hidden="true"></div>
              <h3>From Park City</h3>
              <p>
                Take US-40 South through the Jordanelle area. About 25
                minutes from Old Town Park City to downtown Heber. Beautiful
                drive past the reservoir.
              </p>
            </div>
            <div className="card">
              <div className="card-accent" aria-hidden="true"></div>
              <h3>From Salt Lake</h3>
              <p>
                I-80 East to US-40 South. About 45 miles, 50–60 minutes
                in normal conditions. Sometimes faster via Provo Canyon
                (US-189) if Park City traffic is heavy.
              </p>
            </div>
            <div className="card">
              <div className="card-accent" aria-hidden="true"></div>
              <h3>Getting Around</h3>
              <p>
                A car is essential — Heber Valley is spread out. Most
                attractions are 5–15 minutes apart by car. Midway,
                Charleston, and Heber City all worth visiting.
              </p>
            </div>
          </div>
        </div>

        <div className="cta-banner">
          <h2>See what&apos;s happening this week</h2>
          <p>
            Yoocal aggregates every Heber Valley event — farm tours,
            train rides, festivals, races, classes, and more — updated
            daily.
          </p>
          <a href="/heber" className="cta-btn">
            Browse the calendar →
          </a>
        </div>
      </div>

      <SiteFooter cityLabel="Heber Valley, Utah" />

      <style>{`
        body { font-family: 'DM Sans', sans-serif; background: var(--bg); color: var(--text); overflow-x: hidden; }

        .hero {
          background: var(--dark);
          padding: 120px 80px 80px;
          position: relative; overflow: hidden;
        }
        .hero::before {
          content: ''; position: absolute; inset: 0;
          background: linear-gradient(135deg, #1a1830 0%, #2a2450 50%, #1a1830 100%);
        }
        .hero::after {
          content: ''; position: absolute; inset: 0;
          background: radial-gradient(ellipse 80% 60% at 50% 100%, rgba(83,74,183,0.4) 0%, transparent 70%);
        }
        .hero-inner-hv { position: relative; z-index: 2; max-width: 1200px; margin: 0 auto; display: flex; align-items: flex-start; gap: 60px; }
        .hero-content-hv { flex: 1; min-width: 0; display: flex; flex-direction: column; min-height: 440px; }
        .hero-image-hv { flex: 1; min-width: 0; border-radius: 16px; overflow: hidden; box-shadow: 0 24px 64px rgba(0,0,0,0.5); }
        .hero-image-hv img { width: 100%; height: 440px; object-fit: cover; display: block; }
        .hero-place-title-hv {
          font-family: 'DM Serif Display', serif;
          color: var(--purple-light);
          font-size: clamp(52px, 7vw, 84px);
          font-weight: 400; line-height: 1.04;
          margin-bottom: 44px; display: block;
        }
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
          font-size: clamp(26px, 3.2vw, 40px);
          color: white; line-height: 1.12; margin-bottom: 28px;
        }
        .hero h1 em { font-style: italic; color: var(--purple-light); }
        .hero p {
          font-size: 18px; color: rgba(255,255,255,0.6);
          line-height: 1.7; font-weight: 300; max-width: 560px;
          margin-top: auto;
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

        @media (max-width: 1100px) {
          .hero-inner-hv { flex-direction: column; gap: 24px; align-items: stretch; }
          .hero-content-hv { min-height: 0; }
          .hero p { margin-top: 16px; }
          .hero-image-hv img { height: 320px; }
        }
        @media (max-width: 768px) {
          .hero { padding: 100px 24px 60px; }
          .hero-image-hv img { height: 240px; }
          .content { padding: 48px 24px; }
          .intro { grid-template-columns: 1fr; gap: 40px; }
          .grid-3 { grid-template-columns: 1fr 1fr; }
          .grid-2 { grid-template-columns: 1fr; }
        }
      `}</style>
    </>
  );
}
