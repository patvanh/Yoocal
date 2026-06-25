"use client"

import { useEffect, useRef, useState } from "react"
import { useRouter } from "next/navigation"

/**
 * CityPicker — compact "Current City ▾" pill for the nav bar. Opens a short
 * list of cities; choosing one navigates to that city's calendar via Next
 * routing (same mechanism as CitySearch). Self-contained city list for now;
 * can be consolidated into a shared cities module later.
 */

type City = { key: string; slug: string; label: string }

const CITIES: City[] = [
  { key: "parkcity",    slug: "park-city",    label: "Park City, UT" },
  { key: "heber",       slug: "heber",        label: "Heber Valley, UT" },
  { key: "jackson",     slug: "jackson-hole", label: "Jackson Hole, WY" },
  { key: "elkhartlake", slug: "elkhart-lake", label: "Elkhart Lake, WI" },
  { key: "greenlake",   slug: "green-lake",   label: "Green Lake, WI" },
]

export default function CityPicker({ cityKey }: { cityKey?: string }) {
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const wrapRef = useRef<HTMLDivElement>(null)

  const current = CITIES.find((c) => c.key === cityKey) || CITIES[0]

  useEffect(() => {
    function handler(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [])

  function pick(c: City) {
    setOpen(false)
    if (c.key === current.key) return
    try { window.localStorage.setItem("yoocal.lastCity", c.key) } catch {}
    // Context-aware: keep the user on the same page type, just swap the city.
    const slugs = CITIES.map((x) => x.slug)
    const path = window.location.pathname
    const parts = path.split("/").filter(Boolean)
    const idx = parts.findIndex((p) => slugs.includes(p))
    if (idx !== -1) {
      parts[idx] = c.slug
      router.push("/" + parts.join("/"))
    } else {
      router.push(`/${c.slug}`)
    }
  }

  return (
    <div ref={wrapRef} style={{ position: "relative" }}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        style={{
          display: "flex", alignItems: "center", gap: 4,
          background: "#fff", border: "1.5px solid rgba(83,74,183,0.25)",
          borderRadius: 100, padding: "7px 14px", cursor: "pointer",
          fontFamily: "inherit", fontSize: 12, fontWeight: 600, color: "#3a3550",
          whiteSpace: "nowrap",
        }}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
          <circle cx="12" cy="10" r="3" />
        </svg>
        <span>{current.label}</span>
        <span style={{ fontSize: 10, opacity: 0.7 }}>▾</span>
      </button>
      {open && (
        <div
          role="listbox"
          style={{
            position: "absolute", top: "calc(100% + 6px)", left: 0, minWidth: 180,
            background: "#fff", border: "1px solid rgba(83,74,183,0.15)",
            borderRadius: 12, boxShadow: "0 12px 32px rgba(0,0,0,0.16)",
            padding: 6, zIndex: 1100,
          }}
        >
          {CITIES.map((c) => {
            const active = c.key === current.key
            return (
              <button
                key={c.key}
                type="button"
                role="option"
                aria-selected={active}
                onClick={() => pick(c)}
                style={{
                  display: "block", width: "100%", textAlign: "left",
                  background: active ? "rgba(83,74,183,0.08)" : "transparent",
                  border: "none", borderRadius: 8, padding: "9px 12px",
                  cursor: "pointer", fontFamily: "inherit", fontSize: 13.5,
                  fontWeight: active ? 700 : 500,
                  color: active ? "#534AB7" : "#1e1b3a",
                }}
              >
                {c.label}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
