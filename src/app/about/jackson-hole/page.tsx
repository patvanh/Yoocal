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
        <div className="hero-content">
          <div className="hero-eyebrow">🏔 Jackson Hole, Wyoming · 83001</div>
          <h1>
            Where the <em>mountains</em> meet the world.
          </h1>
          <p>
            6,237 feet in the shadow of the Tetons. World-class festivals,
            a working rodeo, deep snow in winter, and the doorway to Grand
            Teton and Yellowstone National Parks.
          </p>
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
        .hero-content { position: relative; z-index: 2; max-width: 700px; }
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
        }
      `}</style>
    </>
  );
}
