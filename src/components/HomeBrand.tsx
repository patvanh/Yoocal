"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import SiteNav from "@/components/SiteNav"
import SiteFooter from "@/components/SiteFooter"

type City = {
  key: string
  name: string
  region: string
  emoji: string
  blurb: string
  founder?: boolean
}

const CITIES: City[] = [
  {
    key: "parkcity",
    name: "Park City",
    region: "Utah",
    emoji: "⛷️",
    blurb: "Concerts, festivals, races, outdoor adventures and more.",
    founder: true,
  },
  {
    key: "jackson",
    name: "Jackson Hole",
    region: "Wyoming",
    emoji: "🦌",
    blurb: "Music festivals, chamber events, and Teton County happenings.",
  },
  {
    key: "heber",
    name: "Heber Valley",
    region: "Utah",
    emoji: "🏞️",
    blurb: "Rodeos, fairs, train rides and small-town events across the Wasatch Back.",
  },
  {
    key: "elkhartlake",
    name: "Elkhart Lake",
    region: "Wisconsin",
    emoji: "🏁",
    blurb: "Racing, lakeside events and everything around Road America.",
  },
]

export default function HomeBrand() {
  const router = useRouter()
  const [query, setQuery] = useState("")

  function pickCity(key: string) {
    try {
      window.localStorage.setItem("yoocal.lastCity", key)
    } catch {
      // ignore
    }
    router.push(`/?city=${key}`)
  }

  function handleSearch(e: React.FormEvent) {
    e.preventDefault()
    const q = query.trim().toLowerCase()
    if (!q) return
    const match = CITIES.find(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        c.key.toLowerCase() === q ||
        c.region.toLowerCase().includes(q),
    )
    if (match) {
      pickCity(match.key)
    } else {
      router.push(`/request-town?city=${encodeURIComponent(query.trim())}`)
    }
  }

  return (
    <>
      <SiteNav />

      <div className="hb-hero">
        <div className="hb-hero-inner">
          <div className="hb-eyebrow">✦ yoocal</div>
          <h1 className="hb-title">
            Your local,
            <br />
            <em>everywhere.</em>
          </h1>
          <p className="hb-sub">
            One place for everything happening in scenic resort towns and
            mountain communities. Free, updated daily for locals and visitors.
          </p>

          <form className="hb-search" onSubmit={handleSearch}>
            <span className="hb-search-icon">🔍</span>
            <input
              type="text"
              placeholder="Search a city — Park City, Jackson Hole, your hometown…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              autoFocus
            />
            <button type="submit">Go</button>
          </form>
        </div>
      </div>

      <div className="hb-content">
        <div className="hb-section-label">Featured destinations</div>
        <h2 className="hb-section-title">Pick a town to explore</h2>
        <p className="hb-section-sub">
          More cities coming. Don&apos;t see yours? Search above and we&apos;ll
          start tracking it.
        </p>

        <div className="hb-grid">
          {CITIES.map((c) => (
            <button
              key={c.key}
              onClick={() => pickCity(c.key)}
              className="hb-card"
            >
              <div className="hb-card-emoji">{c.emoji}</div>
              <div className="hb-card-info">
                <h3>
                  {c.name}
                  {c.founder && <span className="hb-founder">Where it all began</span>}
                </h3>
                <p className="hb-region">{c.region}</p>
                <p className="hb-blurb">{c.blurb}</p>
              </div>
              <div className="hb-arrow">→</div>
            </button>
          ))}
        </div>

        <div className="hb-cta">
          <h2>
            Don&apos;t see your town?
          </h2>
          <p>
            We&apos;re expanding fast. Tell us where you live and we&apos;ll
            start pulling local events for your community next.
          </p>
          <a href="/request-town" className="hb-cta-btn">
            Submit your town →
          </a>
        </div>
      </div>

      <SiteFooter />

      <style>{`
        body {
          font-family: 'DM Sans', sans-serif;
          background: var(--bg);
          color: var(--text);
          overflow-x: hidden;
        }
        .hb-hero {
          background: var(--dark);
          padding: 140px 80px 90px;
          position: relative;
          overflow: hidden;
          text-align: center;
        }
        .hb-hero::before {
          content: '';
          position: absolute;
          inset: 0;
          background: radial-gradient(ellipse 80% 60% at 50% 100%, rgba(83,74,183,0.4) 0%, transparent 70%);
        }
        .hb-hero-inner { position: relative; z-index: 2; max-width: 760px; margin: 0 auto; }
        .hb-eyebrow {
          display: inline-flex; align-items: center; gap: 8px;
          background: rgba(255,255,255,0.1); color: rgba(255,255,255,0.9);
          font-size: 12px; font-weight: 600; padding: 6px 16px;
          border-radius: 100px; margin-bottom: 28px;
          letter-spacing: 0.5px; border: 1px solid rgba(255,255,255,0.15);
        }
        .hb-title {
          font-family: 'DM Serif Display', serif;
          font-size: clamp(40px, 6vw, 72px);
          color: white; line-height: 1.05; margin-bottom: 24px;
        }
        .hb-title em { font-style: italic; color: #9b8ff0; }
        .hb-sub {
          font-size: 18px; color: rgba(255,255,255,0.6);
          line-height: 1.7; font-weight: 300;
          max-width: 560px; margin: 0 auto 36px;
        }
        .hb-search {
          display: flex; align-items: center; gap: 0;
          background: rgba(255,255,255,0.08);
          border: 1px solid rgba(255,255,255,0.15);
          border-radius: 100px;
          padding: 6px 6px 6px 22px;
          max-width: 560px; margin: 0 auto;
        }
        .hb-search-icon { font-size: 18px; opacity: 0.7; }
        .hb-search input {
          flex: 1;
          background: transparent; border: none;
          color: white;
          font-size: 16px; font-family: inherit;
          padding: 14px 16px; outline: none;
        }
        .hb-search input::placeholder { color: rgba(255,255,255,0.4); }
        .hb-search button {
          background: var(--purple);
          color: white; border: none;
          padding: 12px 28px;
          border-radius: 100px;
          font-size: 14px; font-weight: 600;
          cursor: pointer; transition: background 0.2s;
        }
        .hb-search button:hover { background: var(--purple-light); }

        .hb-content { max-width: 1100px; margin: 0 auto; padding: 80px 40px 120px; }
        .hb-section-label {
          font-size: 12px; font-weight: 700; text-transform: uppercase;
          letter-spacing: 1px; color: var(--amber);
          margin-bottom: 8px; display: flex; align-items: center; gap: 8px;
        }
        .hb-section-label::before {
          content: ''; width: 24px; height: 2px;
          background: var(--purple-light); display: inline-block;
        }
        .hb-section-title {
          font-family: 'DM Serif Display', serif;
          font-size: 36px; margin-bottom: 8px;
        }
        .hb-section-sub {
          font-size: 16px; color: var(--muted); margin-bottom: 36px;
        }

        .hb-grid {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 20px;
          margin-bottom: 80px;
        }
        .hb-card {
          display: flex; align-items: center; gap: 20px;
          background: white; border: 1px solid var(--border);
          border-radius: 20px; padding: 28px;
          text-align: left;
          cursor: pointer;
          font-family: inherit;
          color: inherit;
          transition: all 0.2s;
        }
        .hb-card:hover {
          border-color: var(--purple);
          transform: translateY(-2px);
          box-shadow: 0 12px 32px rgba(83,74,183,0.08);
        }
        .hb-card-emoji { font-size: 40px; flex-shrink: 0; }
        .hb-card-info { flex: 1; }
        .hb-card-info h3 {
          font-size: 18px; font-weight: 600; margin-bottom: 2px;
          display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
        }
        .hb-founder {
          font-size: 10px; font-weight: 700;
          text-transform: uppercase; letter-spacing: 0.6px;
          color: var(--amber);
          background: rgba(244,164,96,0.12);
          padding: 3px 9px;
          border-radius: 100px;
        }
        .hb-region { font-size: 13px; color: var(--muted); margin-bottom: 6px; }
        .hb-blurb { font-size: 13px; color: var(--muted); line-height: 1.5; }
        .hb-arrow { font-size: 22px; color: var(--purple); opacity: 0.6; }
        .hb-card:hover .hb-arrow { opacity: 1; }

        .hb-cta {
          background: var(--dark);
          border-radius: 24px;
          padding: 60px 48px;
          text-align: center;
        }
        .hb-cta h2 {
          font-family: 'DM Serif Display', serif;
          font-size: 32px;
          color: white;
          margin-bottom: 14px;
        }
        .hb-cta p {
          color: rgba(255,255,255,0.55);
          font-size: 16px;
          margin-bottom: 28px;
          max-width: 480px;
          margin-left: auto;
          margin-right: auto;
        }
        .hb-cta-btn {
          display: inline-block;
          background: var(--purple);
          color: white;
          padding: 14px 32px;
          border-radius: 100px;
          font-size: 15px; font-weight: 600;
          text-decoration: none;
          transition: background 0.2s;
        }
        .hb-cta-btn:hover { background: var(--purple-light); }

        @media (max-width: 768px) {
          .hb-hero { padding: 100px 20px 60px; }
          .hb-search { padding: 4px; max-width: 100%; }
          .hb-search input { font-size: 14px; padding: 12px; }
          .hb-search button { padding: 10px 18px; font-size: 13px; }
          .hb-content { padding: 50px 20px 80px; }
          .hb-grid { grid-template-columns: 1fr; gap: 14px; }
          .hb-card { padding: 22px; }
          .hb-cta { padding: 44px 24px; }
        }
      `}</style>
    </>
  )
}
