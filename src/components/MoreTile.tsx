"use client"

import { useEffect, useRef, useState } from "react"

/**
 * MoreTile — a category-tile-styled button that opens a small popover of
 * options. Used for the "More" overflow tiles (extra categories, extra date
 * options) so the white filter panel stays uniform. Matches V2 category tile
 * styling: column layout, icon + label, purple fill when `active`.
 *
 * Props:
 *   label   — tile caption ("More")
 *   Icon    — lucide icon component
 *   active  — whether to show the selected (purple) state
 *   options — [{ label, selected, onClick }] rows shown in the popover
 */

type Option = { label: string; selected?: boolean; onClick: () => void }

export default function MoreTile({
  label,
  Icon,
  active = false,
  options,
}: {
  label: string
  Icon: any
  active?: boolean
  options: Option[]
}) {
  const [open, setOpen] = useState(false)
  const wrapRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handler(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [])

  return (
    <div ref={wrapRef} style={{ position: "relative", display: "flex", flex: "1 1 0", minWidth: 0, maxWidth: 76 }}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        style={{
          display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 4,
          width: "100%", padding: "9px 2px", borderRadius: 12, cursor: "pointer",
          fontFamily: "inherit", fontSize: 10.5, fontWeight: 600, lineHeight: 1.15, textAlign: "center",
          color: active ? "#fff" : "#3a3550",
          background: active ? "#7c5cff" : "transparent",
          border: active ? "1px solid #7c5cff" : "1px solid rgba(26,24,48,0.12)",
          boxShadow: active ? "0 4px 14px rgba(124,92,255,0.35)" : "none",
          transition: "background 0.15s, color 0.15s",
        }}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <Icon size={18} strokeWidth={1.75} />
        <span>{label}</span>
      </button>
      {open && (
        <div
          role="listbox"
          style={{
            position: "absolute", top: "calc(100% + 6px)", left: "50%", transform: "translateX(-50%)",
            minWidth: 170, background: "#fff", border: "1px solid rgba(83,74,183,0.15)",
            borderRadius: 12, boxShadow: "0 12px 32px rgba(0,0,0,0.18)", padding: 6, zIndex: 1100,
          }}
        >
          {options.map((opt) => (
            <button
              key={opt.label}
              type="button"
              role="option"
              aria-selected={!!opt.selected}
              onClick={() => { opt.onClick(); setOpen(false) }}
              style={{
                display: "block", width: "100%", textAlign: "left",
                background: opt.selected ? "rgba(124,92,255,0.10)" : "transparent",
                border: "none", borderRadius: 8, padding: "9px 12px", cursor: "pointer",
                fontFamily: "inherit", fontSize: 13.5,
                fontWeight: opt.selected ? 700 : 500,
                color: opt.selected ? "#534AB7" : "#1e1b3a",
                whiteSpace: "nowrap",
              }}
            >
              {opt.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
