"use client"

import { useEffect, useRef, useState } from "react"

/**
 * RadiusPicker — compact "Within N mi ▾" pill for the nav. Updates the ?radius=
 * URL param (no navigation) and fires a `yoocal:radius` CustomEvent that
 * CalendarClient listens for, so the event list refilters without a reload.
 * Reads its current value from the URL param; stays in sync if the hero radius
 * dropdown changes it (also via the same event).
 */

const OPTIONS = [5, 10, 25, 50]

export default function RadiusPicker() {
  const [open, setOpen] = useState(false)
  const [radius, setRadius] = useState<number>(25)
  const wrapRef = useRef<HTMLDivElement>(null)

  // Initialize from URL + stay in sync when the hero dropdown fires the event.
  useEffect(() => {
    const fromUrl = Number(new URLSearchParams(window.location.search).get("radius"))
    if (OPTIONS.includes(fromUrl)) setRadius(fromUrl)
    const onRadius = (e: Event) => {
      const n = (e as CustomEvent).detail
      if (OPTIONS.includes(n)) setRadius(n)
    }
    window.addEventListener("yoocal:radius", onRadius)
    return () => window.removeEventListener("yoocal:radius", onRadius)
  }, [])

  useEffect(() => {
    function handler(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [])

  function pick(n: number) {
    setOpen(false)
    setRadius(n)
    const u = new URL(window.location.href)
    u.searchParams.set("radius", String(n))
    window.history.replaceState(null, "", u.toString())
    window.dispatchEvent(new CustomEvent("yoocal:radius", { detail: n }))
  }

  return (
    <div ref={wrapRef} style={{ position: "relative" }}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        style={{
          display: "flex", alignItems: "center", gap: 4,
          background: "#fff", border: "1.5px solid rgba(83,74,183,0.25)",
          borderRadius: 100, padding: "5px 10px", cursor: "pointer",
          fontFamily: "inherit", fontSize: 11.5, fontWeight: 600, color: "#534AB7",
          whiteSpace: "nowrap",
        }}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <span>{radius} mi</span>
        <span style={{ fontSize: 10, opacity: 0.7 }}>▾</span>
      </button>
      {open && (
        <div
          role="listbox"
          style={{
            position: "absolute", top: "calc(100% + 6px)", left: 0, minWidth: 130,
            background: "#fff", border: "1px solid rgba(83,74,183,0.15)",
            borderRadius: 12, boxShadow: "0 12px 32px rgba(0,0,0,0.16)",
            padding: 6, zIndex: 1100,
          }}
        >
          {OPTIONS.map((n) => {
            const active = n === radius
            return (
              <button
                key={n}
                type="button"
                role="option"
                aria-selected={active}
                onClick={() => pick(n)}
                style={{
                  display: "block", width: "100%", textAlign: "left",
                  background: active ? "rgba(83,74,183,0.08)" : "transparent",
                  border: "none", borderRadius: 8, padding: "9px 12px",
                  cursor: "pointer", fontFamily: "inherit", fontSize: 13.5,
                  fontWeight: active ? 700 : 500,
                  color: active ? "#534AB7" : "#1e1b3a",
                }}
              >
                Within {n} mi
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
