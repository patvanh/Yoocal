import type { Metadata } from "next";
import SiteNav from "@/components/SiteNav";
import SiteFooter from "@/components/SiteFooter";

export const metadata: Metadata = {
  title: "Page not found — Yoocal",
  description:
    "That page or event couldn't be found — it may have passed or moved. Browse what's happening now across Yoocal's cities.",
  robots: { index: false, follow: true },
};

const CITIES = [
  { href: "/park-city", label: "Park City, Utah" },
  { href: "/jackson-hole", label: "Jackson Hole, Wyoming" },
  { href: "/heber", label: "Heber Valley, Utah" },
  { href: "/elkhart-lake", label: "Elkhart Lake, Wisconsin" },
];

export default function NotFound() {
  return (
    <>
      <SiteNav activeKey={null} />

      <div className="hero">
        <div className="hero-content">
          <div className="hero-eyebrow">404 · Not found</div>
          <h1>
            That page took a <em>different trail</em>.
          </h1>
          <p>
            The page or event you&apos;re looking for couldn&apos;t be found.
            If it was an event, it may have already passed or moved — but
            there&apos;s always something else happening nearby.
          </p>
        </div>
      </div>

      <div className="content">
        <div className="section">
          <div className="section-label">Browse by city</div>
          <h2>See what&apos;s happening now</h2>
          <p className="subtitle">
            Pick a city to jump into a fresh, daily-updated calendar.
          </p>
          <div className="grid-2">
            {CITIES.map((c) => (
              <a key={c.href} href={c.href} className="city-link">
                <span className="city-name">{c.label}</span>
                <span className="city-arrow">→</span>
              </a>
            ))}
          </div>
        </div>

        <div className="cta-banner">
          <h2>Looking for this weekend?</h2>
          <p>
            Jump straight to everything happening Friday through Sunday.
          </p>
          <a href="/this-weekend" className="cta-btn">
            This weekend →
          </a>
        </div>
      </div>

      <SiteFooter />

      <style>{`
        body { font-family: 'DM Sans', sans-serif; background: var(--bg); color: var(--text); overflow-x: hidden; }
        .hero {
          background: var(--dark); padding: 120px 80px 80px;
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
          font-size: 12px; font-weight: 600; padding: 5px 14px;
          border-radius: 100px; margin-bottom: 24px; letter-spacing: 0.5px;
          border: 1px solid rgba(255,255,255,0.15);
        }
        .hero h1 {
          font-family: 'DM Serif Display', serif;
          font-size: clamp(40px, 6vw, 72px); color: white;
          line-height: 1.05; margin-bottom: 20px;
        }
        .hero h1 em { font-style: italic; color: var(--purple-light); }
        .hero p {
          font-size: 18px; color: rgba(255,255,255,0.6);
          line-height: 1.7; font-weight: 300; max-width: 560px;
        }
        .content { max-width: 1100px; margin: 0 auto; padding: 80px 40px; }
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
        .grid-2 { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; }
        .city-link {
          display: flex; align-items: center; justify-content: space-between;
          background: white; border: 1px solid var(--border);
          border-radius: 16px; padding: 24px 28px; text-decoration: none;
          color: var(--text); transition: all 0.2s;
        }
        .city-link:hover {
          border-color: var(--purple); transform: translateY(-2px);
          box-shadow: 0 8px 24px rgba(83,74,183,0.08);
        }
        .city-name { font-size: 17px; font-weight: 600; }
        .city-arrow { color: var(--purple); font-size: 18px; }
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
          display: inline-block; background: var(--purple); color: white;
          padding: 14px 32px; border-radius: 100px; font-size: 15px;
          font-weight: 600; text-decoration: none;
        }
        .cta-btn:hover { background: var(--purple-light); }
        @media (max-width: 768px) {
          .hero { padding: 100px 24px 60px; }
          .content { padding: 48px 24px; }
          .grid-2 { grid-template-columns: 1fr; }
          .cta-banner { padding: 40px 24px; }
        }
      `}</style>
    </>
  );
}
