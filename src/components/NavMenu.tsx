"use client"

import { useEffect, useRef, useState } from "react"

export type NavLink = { href: string; label: string; active?: boolean; external?: boolean }

export default function NavMenu({ links }: { links: NavLink[] }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    function onDown(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener("mousedown", onDown)
    return () => document.removeEventListener("mousedown", onDown)
  }, [open])

  const bar = { display: "block", width: 22, height: 2, background: "#3a3550", borderRadius: 2 } as const

  return (
    <div className="yc-hamburger" ref={ref} style={{ position: "relative" }}>
      <button
        aria-label="Menu"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        style={{ display: "flex", flexDirection: "column", justifyContent: "center", gap: 4, width: 40, height: 40, padding: 0, background: "transparent", border: "none", cursor: "pointer" }}
      >
        <span style={bar} />
        <span style={bar} />
        <span style={bar} />
      </button>

      {open ? (
        <div style={{ position: "absolute", top: "calc(100% + 8px)", right: 0, background: "#fff", border: "1px solid rgba(83,74,183,0.15)", borderRadius: 12, boxShadow: "0 12px 32px rgba(0,0,0,0.16)", padding: 8, minWidth: 220, zIndex: 1200, display: "flex", flexDirection: "column" }}>
          {links.map((l) => (
            <a key={l.href + l.label} href={l.href} target={l.external ? "_blank" : undefined} rel={l.external ? "noopener noreferrer" : undefined} onClick={() => setOpen(false)} style={{ padding: "10px 14px", borderRadius: 8, textDecoration: "none", fontFamily: "inherit", fontSize: 14, fontWeight: 500, color: l.active ? "#534AB7" : "#1e1b3a" }}>
              {l.label}
            </a>
          ))}
        </div>
      ) : null}
    </div>
  )
}
