"use client"

import { useEffect, useRef, useState } from "react"
import { useRouter } from "next/navigation"
import SiteNav from "@/components/SiteNav"
import SiteFooter from "@/components/SiteFooter"
import { buildCityOptions } from "@/lib/citySearch"

type City = {
  key: string
  name: string
  region: string
  emoji: string
  image?: string
  blurb: string
  founder?: boolean
}

const CITIES: City[] = [
  {
    key: "parkcity",
    image: "/cities/parkcity.jpg",
    name: "Park City",
    region: "Utah",
    emoji: "",
    blurb: "Concerts, festivals, races, outdoor adventures and more.",
    founder: true,
  },
  {
    key: "jackson",
    image: "/cities/jackson.jpg",
    name: "Jackson Hole",
    region: "Wyoming",
    emoji: "",
    blurb: "Music festivals, chamber events, and Teton County happenings.",
  },
  {
    key: "heber",
    image: "/cities/heber.jpg",
    name: "Heber Valley",
    region: "Utah",
    emoji: "",
    blurb: "Rodeos, fairs, train rides and small-town events across the Wasatch Back.",
  },
  {
    key: "elkhartlake",
    image: "/cities/elkhartlake.jpg",
    name: "Elkhart Lake",
    region: "Wisconsin",
    emoji: "",
    blurb: "Racing, lakeside events and everything around Road America.",
  },
  {
    key: "greenlake",
    image: "/cities/greenlake.jpg",
    name: "Green Lake",
    region: "Wisconsin",
    emoji: "",
    blurb: "Golf, boating, summer concerts and small-town events on Wisconsin’s deepest lake.",
  },
]

// ZIP -> city key. Small static map for the 4 live cities; expand as we grow.
const ZIP_TO_CITY: Record<string, string> = {
  // Park City + surrounding
  "84060": "parkcity",
  "84068": "parkcity",
  "84098": "parkcity",
  // Jackson Hole + Teton County
  "83001": "jackson",
  "83002": "jackson",
  "83014": "jackson",
  "83025": "jackson",
  // Heber Valley
  "84032": "heber",
  "84049": "heber",
  // Elkhart Lake
  "53020": "elkhartlake",
}

// Aliases — typing these resolves to the matching city
const ALIASES: Record<string, string> = {
  "pc": "parkcity",
  "park city ut": "parkcity",
  "jh": "jackson",
  "jackson wy": "jackson",
  "midway": "heber",
  "wasatch back": "heber",
  "road america": "elkhartlake",
}

type SearchOption =
  | { kind: "city"; city: City }
  | { kind: "request"; rawQuery: string }

export default function HomeBrand() {
  const router = useRouter()
  const [query, setQuery] = useState("")
  const [open, setOpen] = useState(false)
  const [activeIdx, setActiveIdx] = useState(0)
  const wrapRef = useRef<HTMLDivElement>(null)
  const [email, setEmail] = useState("")
  const [subState, setSubState] = useState<"idle" | "loading" | "done" | "error">("idle")
  async function handleSubscribe(e: React.FormEvent) {
    e.preventDefault()
    const v = email.trim()
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v)) { setSubState("error"); return }
    setSubState("loading")
    try {
      const r = await fetch("/api/subscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: v }),
      })
      setSubState(r.ok ? "done" : "error")
    } catch {
      setSubState("error")
    }
  }

  function pickCity(key: string) {
    try {
      window.localStorage.setItem("yoocal.lastCity", key)
    } catch {
      // ignore
    }
    router.push(`/${({parkcity:"park-city",elkhartlake:"elkhart-lake",heber:"heber",jackson:"jackson-hole",greenlake:"green-lake"} as Record<string,string>)[key] || ""}`)
  }

  // Strip ", UT" or ", Wyoming" and similar suffixes for cleaner matching
  function normalizeQuery(raw: string): string {
    return raw
      .toLowerCase()
      .trim()
      .replace(/,\s*[a-z .]+$/, "") // drop trailing state suffix
      .replace(/\s+/g, " ")
  }

  function buildOptions(raw: string): SearchOption[] {
    const trimmed = raw.trim()
    if (!trimmed) return []

    // ZIP shortcut: 5-digit -> direct city
    const zipOnly = trimmed.match(/^\d{5}$/)
    if (zipOnly) {
      const k = ZIP_TO_CITY[trimmed]
      if (k) {
        const c = CITIES.find((x) => x.key === k)
        if (c) return [{ kind: "city", city: c }]
      }
      // Unknown ZIP -> request
      return [{ kind: "request", rawQuery: trimmed }]
    }

    const q = normalizeQuery(trimmed)

    // Alias direct hit
    if (ALIASES[q]) {
      const c = CITIES.find((x) => x.key === ALIASES[q])
      if (c) return [{ kind: "city", city: c }]
    }

    // Substring match against name + region + key
    const matches = CITIES.filter((c) => {
      const hay = `${c.name} ${c.region} ${c.key}`.toLowerCase()
      return hay.includes(q)
    })

    const opts: SearchOption[] = matches.map((c) => ({ kind: "city", city: c }))
    // Always offer a request fallback at the end so unknown queries route correctly
    opts.push({ kind: "request", rawQuery: trimmed })
    return opts
  }

  const options = buildCityOptions(query)
  // Keep activeIdx in bounds when options change
  useEffect(() => {
    if (activeIdx >= options.length) setActiveIdx(0)
  }, [options.length, activeIdx])

  // Click outside to close dropdown
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [])

  function chooseOption(opt: SearchOption) {
    if (opt.kind === "city") {
      pickCity(opt.city.key)
    } else {
      router.push(`/request-town?city=${encodeURIComponent(opt.rawQuery)}`)
    }
    setOpen(false)
  }

  function handleSearch(e: React.FormEvent) {
    e.preventDefault()
    if (!query.trim()) return
    const opt = options[activeIdx] ?? options[0]
    if (opt) chooseOption(opt)
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (!open || options.length === 0) return
    if (e.key === "ArrowDown") {
      e.preventDefault()
      setActiveIdx((i) => (i + 1) % options.length)
    } else if (e.key === "ArrowUp") {
      e.preventDefault()
      setActiveIdx((i) => (i - 1 + options.length) % options.length)
    } else if (e.key === "Escape") {
      setOpen(false)
    }
  }

  return (
    <>
      <SiteNav />

      <div className="hb-hero">
        <div className="hb-hero-inner">
          <div className="hb-eyebrow">yoocal</div>
          <h1 className="hb-title">
            Your local,
            <br />
            <em>everywhere.</em>
          </h1>
          <p className="hb-sub">
            One place for everything happening in scenic resort towns and
            mountain communities. Free, updated daily for locals and visitors.
          </p>

          <div className="hb-search-wrap" ref={wrapRef}>
            <form className="hb-search" onSubmit={handleSearch}>
              
              <input
                type="text"
                placeholder="Search a city, town, or ZIP — try 'Park City' or '84060'"
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value)
                  setOpen(true)
                  setActiveIdx(0)
                }}
                onFocus={() => setOpen(true)}
                onKeyDown={handleKeyDown}
                autoFocus
              />
              <button type="submit">Go</button>
            </form>

            {open && options.length > 0 && (
              <ul className="hb-suggest" role="listbox">
                {options.map((opt, i) => (
                  <li
                    key={opt.kind === "city" ? `c-${opt.city.key}` : `r-${i}`}
                    role="option"
                    aria-selected={i === activeIdx}
                    className={i === activeIdx ? "active" : ""}
                    onMouseEnter={() => setActiveIdx(i)}
                    onMouseDown={(e) => {
                      // mousedown so it fires before input blur closes the dropdown
                      e.preventDefault()
                      chooseOption(opt)
                    }}
                  >
                    {opt.kind === "city" ? (
                      <>
                        
                        <span className="hb-suggest-name">{opt.city.name}</span>
                        <span className="hb-suggest-region">{opt.city.region}</span>
                      </>
                    ) : (
                      <>
                        <span className="hb-suggest-emoji">📍</span>
                        <span className="hb-suggest-name">
                          Request <strong>{opt.rawQuery}</strong>
                        </span>
                        <span className="hb-suggest-region">Not in network yet</span>
                      </>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
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
              style={c.image ? { backgroundImage: `linear-gradient(to top, rgba(15,12,35,0.85) 0%, rgba(15,12,35,0.3) 42%, rgba(15,12,35,0) 70%), url(${c.image})` } : undefined}
            >
              
              <div className="hb-card-info">
                <h3>
                  {c.name}
                  {c.founder && <span className="hb-founder">Where it all began</span>}
                </h3>
                <p className="hb-region">{c.region}</p>
              </div>
            </button>
          ))}
        </div>

        <div className="hb-how">
          <div className="hb-how-item">
            <div className="hb-how-num">1</div>
            <h3>Pick your town</h3>
            <p>Four mountain &amp; lake towns live now, with more on the way.</p>
          </div>
          <div className="hb-how-item">
            <div className="hb-how-num">2</div>
            <h3>See everything happening</h3>
            <p>Concerts, festivals, races and more &mdash; every source in one place, refreshed daily.</p>
          </div>
          <div className="hb-how-item">
            <div className="hb-how-num">3</div>
            <h3>Never miss out</h3>
            <p>Always free. Get the week&apos;s best events in your inbox.</p>
          </div>
        </div>

        <div className="hb-duo">
        <div className="hb-news">
          <h2>Get the week&apos;s best events in your inbox</h2>
          <p>A short weekly email with the can&apos;t-miss happenings in your town. Free, no spam.</p>
          {subState === "done" ? (
            <div className="hb-news-done">You&apos;re in &mdash; check your inbox soon. ✦</div>
          ) : (
            <form className="hb-news-form" onSubmit={handleSubscribe}>
              <input
                type="email"
                value={email}
                onChange={(e) => { setEmail(e.target.value); if (subState === "error") setSubState("idle") }}
                placeholder="you@email.com"
                aria-label="Email address"
              />
              <button type="submit" disabled={subState === "loading"}>
                {subState === "loading" ? "Joining…" : "Notify me"}
              </button>
            </form>
          )}
          {subState === "error" && <div className="hb-news-err">Please enter a valid email and try again.</div>}
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
          background: linear-gradient(180deg, rgba(26,24,48,0.55), rgba(26,24,48,0.70)), url('/home-hero.jpg') center/cover no-repeat;
          padding: 92px 80px 72px;
          position: relative;
          overflow: visible;        /* let the search dropdown escape the hero */
          overflow-x: clip;          /* but still prevent horizontal scroll */
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

        .hb-search-wrap { position: relative; max-width: 560px; margin: 0 auto; }
        .hb-suggest {
          position: absolute; top: calc(100% + 8px); left: 0; right: 0;
          background: white;
          border: 1px solid var(--border);
          border-radius: 14px;
          box-shadow: 0 16px 40px rgba(14,10,38,0.18);
          padding: 8px; margin: 0;
          list-style: none;
          z-index: 20;
          text-align: left;
          max-height: 280px; overflow-y: auto;
        }
        .hb-suggest li {
          display: flex; align-items: center; gap: 12px;
          padding: 10px 12px;
          border-radius: 10px;
          cursor: pointer;
          font-size: 14px;
          color: var(--text);
        }
        .hb-suggest li.active,
        .hb-suggest li:hover {
          background: rgba(83,74,183,0.08);
        }
        .hb-suggest-emoji { font-size: 20px; flex-shrink: 0; }
        .hb-suggest-name { flex: 1; }
        .hb-suggest-region {
          font-size: 12px; color: var(--muted);
        }

        .hb-content { max-width: 1100px; margin: 0 auto; padding: 40px 40px 40px; }
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
          position: relative;
          display: flex; flex-direction: column; justify-content: flex-end;
          aspect-ratio: 16 / 9;
          background-color: #2a2545; background-size: cover; background-position: center;
          border: 1px solid var(--border);
          border-radius: 20px; padding: 22px;
          text-align: left;
          cursor: pointer;
          font-family: inherit;
          color: #fff;
          overflow: hidden;
          transition: transform 0.2s, box-shadow 0.2s;
        }
        .hb-card:hover {
          transform: translateY(-3px);
          box-shadow: 0 16px 40px rgba(83,74,183,0.18);
        }
        .hb-card-fallback {
          position: absolute; inset: 0;
          display: flex; align-items: center; justify-content: center;
          font-size: 72px; opacity: 0.45;
        }
        .hb-card-info { position: relative; z-index: 1; }
        .hb-card-info h3 {
          font-size: 22px; font-weight: 700; margin-bottom: 2px; color: #fff;
          display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
        }
        .hb-founder {
          font-size: 10px; font-weight: 700;
          text-transform: uppercase; letter-spacing: 0.6px;
          color: var(--amber);
          background: rgba(244,164,96,0.18);
          padding: 3px 9px;
          border-radius: 100px;
        }
        .hb-region { font-size: 13px; color: rgba(255,255,255,0.8); margin-bottom: 0; }

        .hb-how { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 28px; margin: 4px 0 56px; }
        .hb-how-item { text-align: left; }
        .hb-how-num { width: 34px; height: 34px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 15px; color: var(--purple); background: rgba(83,74,183,0.1); margin-bottom: 14px; }
        .hb-how-item h3 { font-size: 17px; font-weight: 600; margin-bottom: 6px; color: var(--dark); }
        .hb-how-item p { font-size: 14px; color: var(--muted); line-height: 1.6; }
        .hb-duo { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 20px; margin-bottom: 0; align-items: stretch; }
        .hb-news { background: var(--dark); border-radius: 24px; padding: clamp(36px, 5vw, 56px) clamp(24px, 5vw, 48px); text-align: center; display: flex; flex-direction: column; justify-content: center; }
        .hb-news h2 { font-family: 'DM Serif Display', serif; font-size: clamp(24px, 3vw, 34px); color: #fff; margin-bottom: 10px; }
        .hb-news > p { font-size: 15px; color: rgba(255,255,255,0.6); margin-bottom: 26px; }
        .hb-news-form { display: flex; gap: 10px; max-width: 460px; margin: 0 auto; flex-wrap: wrap; justify-content: center; }
        .hb-news-form input { flex: 1; min-width: 220px; padding: 14px 18px; font-size: 15px; font-family: inherit; border-radius: 100px; border: 1px solid rgba(255,255,255,0.18); background: rgba(255,255,255,0.08); color: #fff; outline: none; }
        .hb-news-form input::placeholder { color: rgba(255,255,255,0.4); }
        .hb-news-form input:focus { border-color: rgba(155,143,240,0.6); }
        .hb-news-form button { padding: 14px 26px; font-size: 15px; font-weight: 700; font-family: inherit; border: none; border-radius: 100px; background: var(--purple); color: #fff; cursor: pointer; }
        .hb-news-form button:hover { background: #6E64C9; }
        .hb-news-form button:disabled { opacity: 0.6; cursor: default; }
        .hb-news-done { font-size: 16px; font-weight: 600; color: #fff; }
        .hb-news-err { font-size: 13px; color: #ffb4b4; margin-top: 12px; }
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
