import type { Metadata } from "next";
import SiteNav from "@/components/SiteNav";
import SiteFooter from "@/components/SiteFooter";

export const metadata: Metadata = {
  title: "About Jackson Hole, Wyoming — Yoocal",
  description:
    "Everything happening in Jackson Hole, Wyoming. Grand Teton Music Festival, Snow King concerts, Teton County Fair, the rodeo, and the gateway to Grand Teton and Yellowstone.",
  alternates: { canonical: "https://www.yoocal.com/about/jackson-hole" },
  openGraph: {
    title: "About Jackson Hole, Wyoming — Yoocal",
    description:
      "Grand Teton Music Festival, the rodeo, Snow King concerts, Teton County Fair, and the gateway to two of America's greatest national parks.",
    url: "https://www.yoocal.com/about/jackson-hole",
    type: "website",
  },
};

export default function AboutJacksonHolePage() {
  return (
    <>
      <SiteNav activeKey="about" cityKey="jackson" />

      <div className="hero">
        <div className="hero-inner-jh">
          <div className="hero-content-jh">
            <div className="hero-place-title-jh">Jackson Hole, Wyoming</div>
            <h1>
              Where the <em>mountains</em> meet the world.
            </h1>
            <p>
              6,237 feet in the shadow of the Tetons. World-class festivals,
              a working rodeo, deep snow in winter, and the doorway to Grand
              Teton and Yellowstone National Parks.
            </p>
          </div>
          <div className="hero-image-jh"><img src="/jackson.jpg" alt="Jackson Hole, Wyoming valley at sunset" /></div>
        </div>
      </div>

      <div className="content">
        <div className="intro">
          <div className="intro-text">
            <h2>Welcome to Jackson Hole</h2>
            <p>
              Jackson Hole isn&apos;t actually a town — it&apos;s the valley.
              The town at its heart is Jackson, but the whole valley
              between the Tetons and the Gros Ventre Range carries the
              name. Year-round, it&apos;s a place where small-town western
              life happens at the foot of some of the most dramatic
              mountains on the continent.
            </p>
            <p>
              Summer is festival season — the Grand Teton Music Festival
              brings world-class orchestral programs to Walk Festival Hall
              in Teton Village for seven weeks. The Jackson Hole Rodeo
              runs all summer at the fairgrounds. King Concerts light up
              Snow King Mountain. The Teton County Fair fills late July.
              Winter is skiing — Jackson Hole Mountain Resort, Snow King,
              and Grand Targhee — plus the National Elk Refuge sleigh
              rides and ice climbing. Yoocal pulls together everything
              happening in the valley into one daily-updated calendar.
            </p>
          </div>
          <div className="intro-stats">
            <div className="stat-card">
              <span className="num">
                6,237<small style={{ fontSize: 16 }}>ft</small>
              </span>
              <span className="label">Elevation</span>
            </div>
            <div className="stat-card">
              <span className="num">~10K</span>
              <span className="label">Jackson population</span>
            </div>
            <div className="stat-card">
              <span className="num">2</span>
              <span className="label">National parks at the door</span>
            </div>
            <div className="stat-card">
              <span className="num">459&quot;</span>
              <span className="label">Average snow / yr</span>
            </div>
          </div>
        </div>

        <div className="section">
          <div className="section-label">Explore</div>
          <h2>Things to do in Jackson Hole</h2>
          <p className="subtitle">
            From the Tetons to the town square — there&apos;s always
            something happening in the valley.
          </p>
          <div className="grid-3">
            <div className="card">
              <div className="card-accent" aria-hidden="true"></div>
              <h3>Festivals &amp; Music</h3>
              <p>
                The Grand Teton Music Festival brings world-class orchestral
                programs to Walk Festival Hall for seven weeks each summer.
                Center for the Arts and Snow King concerts run year-round.
              </p>
            </div>
            <div className="card">
              <div className="card-accent" aria-hidden="true"></div>
              <h3>Rodeo &amp; Western Life</h3>
              <p>
                The Jackson Hole Rodeo runs all summer at the fairgrounds.
                The Teton County Fair fills late July with livestock shows,
                a carnival, and a working slice of Wyoming ranch culture.
              </p>
            </div>
            <div className="card">
              <div className="card-accent" aria-hidden="true"></div>
              <h3>National Parks</h3>
              <p>
                Grand Teton National Park is minutes away and Yellowstone is
                just north — two of America&apos;s greatest parks at the
                valley&apos;s doorstep for hiking, wildlife, and scenery.
              </p>
            </div>
            <div className="card">
              <div className="card-accent" aria-hidden="true"></div>
              <h3>Skiing &amp; Snow</h3>
              <p>
                Jackson Hole Mountain Resort, Snow King, and nearby Grand
                Targhee deliver some of the deepest, steepest terrain in the
                country — an average of 459&quot; of snow a year.
              </p>
            </div>
            <div className="card">
              <div className="card-accent" aria-hidden="true"></div>
              <h3>Wildlife &amp; Winter</h3>
              <p>
                The National Elk Refuge offers winter sleigh rides among
                thousands of elk. Ice climbing, fat biking, and Nordic
                trails round out the cold-season calendar.
              </p>
            </div>
            <div className="card">
              <div className="card-accent" aria-hidden="true"></div>
              <h3>Arts &amp; Galleries</h3>
              <p>
                The National Museum of Wildlife Art, the Center for the Arts,
                and a dense gallery scene around the town square make Jackson
                a serious arts destination, not just an outdoor one.
              </p>
            </div>
          </div>
        </div>

        <div className="section">
          <div className="section-label">When to go</div>
          <h2>Best times to visit Jackson Hole</h2>
          <p className="subtitle">
            A true four-season valley — each one a different trip.
          </p>
          <div className="season-grid">
            <div className="season">
              <div className="season-accent" aria-hidden="true"></div>
              <h3>Winter (Dec–Mar)</h3>
              <p>
                Peak ski season and deep snow. Elk refuge sleigh rides, ice
                climbing, and quiet town nights. Book early around the
                holidays.
              </p>
            </div>
            <div className="season">
              <div className="season-accent" aria-hidden="true"></div>
              <h3>Spring (Apr–May)</h3>
              <p>
                Mud season — the quietest, cheapest window. Parks begin
                reopening roads and wildlife is active as the valley thaws.
              </p>
            </div>
            <div className="season">
              <div className="season-accent" aria-hidden="true"></div>
              <h3>Summer (Jun–Sep)</h3>
              <p>
                Festival season. The Grand Teton Music Festival, the rodeo,
                fairs, and full access to both national parks. Warm days,
                cool nights — the busiest and best window.
              </p>
            </div>
            <div className="season">
              <div className="season-accent" aria-hidden="true"></div>
              <h3>Fall (Oct–Nov)</h3>
              <p>
                Golden aspens, the elk rut, and far fewer people. A
                spectacular, calmer time before the ski resorts spin up.
              </p>
            </div>
          </div>
        </div>

        <div className="cta-banner">
          <h2>See what&apos;s happening this week</h2>
          <p>
            Yoocal aggregates every Jackson Hole event — orchestras,
            rodeos, festivals, concerts, races, and more — updated daily.
          </p>
          <a href="/jackson-hole" className="cta-btn">
            Browse the calendar →
          </a>
        </div>
      </div>

      <SiteFooter cityLabel="Jackson Hole, Wyoming" />

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
        .hero-inner-jh { position: relative; z-index: 2; max-width: 1200px; margin: 0 auto; display: flex; align-items: flex-start; gap: 60px; }
        .hero-content-jh { flex: 1; min-width: 0; display: flex; flex-direction: column; min-height: 440px; }
        .hero-image-jh { flex: 1; min-width: 0; border-radius: 16px; overflow: hidden; box-shadow: 0 24px 64px rgba(0,0,0,0.5); }
        .hero-image-jh img { width: 100%; height: 440px; object-fit: cover; display: block; }
        .hero-place-title-jh {
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
        .section h2 { font-family: 'DM Serif Display', serif; font-size: 32px; margin-bottom: 8px; }
        .section .subtitle { font-size: 16px; color: var(--muted); margin-bottom: 32px; }
        .grid-3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }
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

        @media (max-width: 1100px) {
          .hero-inner-jh { flex-direction: column; gap: 24px; align-items: stretch; }
          .hero-content-jh { min-height: 0; }
          .hero p { margin-top: 16px; }
          .hero-image-jh img { height: 320px; }
        }
        @media (max-width: 768px) {
          .hero { padding: 100px 24px 60px; }
          .hero-image-jh img { height: 240px; }
          .content { padding: 48px 24px; }
          .intro { grid-template-columns: 1fr; gap: 40px; }
          .grid-3, .season-grid { grid-template-columns: 1fr 1fr; }
        }
      `}</style>
    </>
  );
}
