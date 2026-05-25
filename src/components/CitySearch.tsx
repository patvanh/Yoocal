"use client"

import { useEffect, useRef, useState } from "react"
import { useRouter } from "next/navigation"
import { buildCityOptions, type SearchOption } from "@/lib/citySearch"

type Props = {
  placeholder?: string
  variant?: "hero" | "compact"
}

/**
 * Shared city/ZIP search with a suggestions dropdown. Used on the home page
 * and on city calendar pages so the experience is identical. Typing a city
 * name, alias, full ZIP, or ZIP prefix ("840") surfaces matching cities;
 * choosing one navigates to that city's calendar.
 */
export default function CitySearch({ placeholder, variant = "compact" }: Props) {
  const router = useRouter()
  const [query, setQuery] = useState("")
  const [open, setOpen] = useState(false)
  const [activeIdx, setActiveIdx] = useState(0)
  const wrapRef = useRef<HTMLDivElement>(null)

  const options = buildCityOptions(query)

  useEffect(() => {
    if (activeIdx >= options.length) setActiveIdx(0)
  }, [options.length, activeIdx])

  useEffect(() => {
    function handler(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [])

  function pickCity(key: string) {
    try { window.localStorage.setItem("yoocal.lastCity", key) } catch {}
    router.push(`/?city=${key}`)
  }

  function chooseOption(opt: SearchOption) {
    if (opt.kind === "city") pickCity(opt.city.key)
    else router.push(`/request-town?city=${encodeURIComponent(opt.rawQuery)}`)
    setOpen(false)
    setQuery("")
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!query.trim()) return
    const opt = options[activeIdx] ?? options[0]
    if (opt) chooseOption(opt)
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (!open || options.length === 0) return
    if (e.key === "ArrowDown") { e.preventDefault(); setActiveIdx((i) => (i + 1) % options.length) }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActiveIdx((i) => (i - 1 + options.length) % options.length) }
    else if (e.key === "Escape") setOpen(false)
  }

  return (
    <div className="cs-wrap" ref={wrapRef}>
      <form className="cs-form" onSubmit={handleSubmit}>
        <span className="cs-icon">🔍</span>
        <input
          className="v2-search-input cs-input"
          type="text"
          value={query}
          placeholder={placeholder || "Search a city, town, or ZIP — try 'Park City' or '84060'"}
          onChange={(e) => { setQuery(e.target.value); setOpen(true) }}
          onFocus={() => setOpen(true)}
          onKeyDown={handleKeyDown}
        />
      </form>
      {open && options.length > 0 && (
        <div className="cs-dropdown">
          {options.map((opt, i) => (
            <button
              key={opt.kind === "city" ? `c-${opt.city.key}` : `r-${i}`}
              type="button"
              className={`cs-option${i === activeIdx ? " active" : ""}`}
              onMouseEnter={() => setActiveIdx(i)}
              onMouseDown={(e) => { e.preventDefault(); chooseOption(opt) }}
            >
              {opt.kind === "city" ? (
                <>
                  <span className="cs-emoji">{opt.city.emoji}</span>
                  <span className="cs-name">{opt.city.name}</span>
                  <span className="cs-region">{opt.city.region}</span>
                </>
              ) : (
                <>
                  <span className="cs-emoji">📍</span>
                  <span className="cs-name">Request “{opt.rawQuery}”</span>
                  <span className="cs-region">Not live yet</span>
                </>
              )}
            </button>
          ))}
        </div>
      )}
      <style jsx>{`
        .cs-wrap { position: relative; width: 100%; }
        .cs-form { display: flex; align-items: center; position: relative; }
        .cs-icon {
          position: absolute; left: 13px; font-size: 13px; opacity: 0.55;
          pointer-events: none; z-index: 1;
        }
        .cs-input {
          width: 100%; padding: 7px 14px 7px 34px !important; font-size: 13px;
          border-radius: 999px; background: rgba(255,255,255,0.06); color: #fff;
          border: 1px solid rgba(255,255,255,0.18); outline: none;
          font-family: 'DM Sans', sans-serif; box-sizing: border-box;
        }
        .cs-input:focus { border-color: rgba(127,119,221,0.7); background: rgba(255,255,255,0.09); }
        .cs-input::placeholder { color: rgba(255,255,255,0.4); }
        .cs-dropdown {
          position: absolute; top: calc(100% + 8px); left: 0; right: 0; z-index: 100;
          background: #211a45; border: 1px solid rgba(175,169,236,0.28);
          border-radius: 14px; overflow: hidden; padding: 5px;
          box-shadow: 0 16px 40px rgba(0,0,0,0.5);
        }
        .cs-option {
          display: flex; align-items: center; gap: 10px; width: 100%;
          padding: 10px 12px; background: transparent; border: none; cursor: pointer;
          text-align: left; color: #fff; font-family: 'DM Sans', sans-serif;
          font-size: 14px; border-radius: 9px;
        }
        .cs-option.active, .cs-option:hover { background: rgba(127,119,221,0.28); }
        .cs-emoji { font-size: 17px; flex-shrink: 0; }
        .cs-name { font-weight: 600; }
        .cs-region { margin-left: auto; font-size: 12px; color: rgba(255,255,255,0.45); }
      `}</style>
    </div>
  )
}
