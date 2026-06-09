"use client";

import { useMemo, useState } from "react";
import EventModal, { type EventModalData } from "@/components/EventModal";

const CAT_COLOR: Record<string, string> = {
  "Music": "#7c5cff", "Arts & Theater": "#d6457a", "Food & Drink": "#e0892a",
  "Outdoors": "#2fa36b", "Running & Races": "#e0892a", "Sports": "#2f7fa3",
  "Family & Kids": "#c0489b", "Wellness": "#3aa39a", "Nightlife": "#9b51e0",
  "Education & Talks": "#5566c4", "Community": "#6b61d6",
};
function accentFor(ev: EventModalData): string {
  for (const c of ev.categories || []) if (CAT_COLOR[c]) return CAT_COLOR[c];
  return "#6b61d6";
}
const MONTHS = ["January","February","March","April","May","June","July","August","September","October","November","December"];
const MON3 = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
const WD = ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"];
const iso2 = (n: number) => String(n).padStart(2, "0");
function parseIso(iso: string) { const [y,m,d] = iso.split("-").map(Number); return new Date(y, m-1, d); }

export default function IntentDayList({ events, variant = "month", citySlug }: { events: EventModalData[]; variant?: "month" | "columns"; citySlug?: string }) {
  const [active, setActive] = useState<EventModalData | null>(null);
  const [query, setQuery] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);
  const todayIso = new Date().toISOString().slice(0, 10);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return events;
    return events.filter((e) =>
      `${e.title || ""} ${e.location || ""} ${e.description || ""} ${e.source || ""}`.toLowerCase().includes(q)
    );
  }, [events, query]);

  const byDate = useMemo(() => {
    const m: Record<string, EventModalData[]> = {};
    for (const e of filtered) { const d = (e.date || "").slice(0, 10); if (!d) continue; (m[d] = m[d] || []).push(e); }
    return m;
  }, [filtered]);

  const [cursor, setCursor] = useState(() => {
    const isos = events.map((e) => (e.date || "").slice(0, 10)).filter(Boolean).sort();
    const base = isos[0] || new Date().toISOString().slice(0, 10);
    const [y, m] = base.split("-").map(Number);
    return { y, m: m - 1 };
  });
  const cells = useMemo(() => {
    const pad = new Date(cursor.y, cursor.m, 1).getDay();
    const days = new Date(cursor.y, cursor.m + 1, 0).getDate();
    const out: ({ d: number; iso: string; events: EventModalData[] } | null)[] = [];
    for (let i = 0; i < pad; i++) out.push(null);
    for (let d = 1; d <= days; d++) { const k = `${cursor.y}-${iso2(cursor.m + 1)}-${iso2(d)}`; out.push({ d, iso: k, events: byDate[k] || [] }); }
    while (out.length % 7 !== 0) out.push(null);
    return out;
  }, [cursor, byDate]);
  const monthCount = cells.reduce((n, c) => n + (c ? c.events.length : 0), 0);
  const step = (delta: number) => { setExpanded(null); setCursor((c) => { const dt = new Date(c.y, c.m + delta, 1); return { y: dt.getFullYear(), m: dt.getMonth() }; }); };

  const dayCols = useMemo(() => Object.keys(byDate).sort().map((iso) => ({ iso, events: byDate[iso] })), [byDate]);

  const search = (
    <div className="i-search">
      <input type="text" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search by name, venue, or artist..." />
      <span className="i-count">{filtered.length} {filtered.length === 1 ? "event" : "events"}</span>
    </div>
  );
  const srList = (
    <ul className="i-sr">
      {events.map((e, i) => (<li key={`sr${i}`}><a href={(citySlug && (e as any).detailSlug ? `/${citySlug}/${(e as any).detailSlug}` : e.link) || "#"}>{e.title}</a> &mdash; {(e.date || "").slice(0, 10)}{e.location ? ` — ${e.location}` : ""}</li>))}
    </ul>
  );

  return (
    <div className="iw">
      {search}

      {variant === "columns" ? (
        <>
          <div className="cl">
            {dayCols.map((col) => {
              const dt = parseIso(col.iso);
              return (
                <div className="cl-col" key={col.iso}>
                  <div className="cl-head">
                    <span className="cl-wd">{WD[dt.getDay()]}</span>
                    <span className="cl-md">{MON3[dt.getMonth()]} {dt.getDate()}</span>
                  </div>
                  <div className="cl-evs">
                    {col.events.map((ev, k) => (
                      <a key={`${col.iso}-${k}`} href={citySlug && (ev as any).detailSlug ? `/${citySlug}/${(ev as any).detailSlug}` : undefined} className="cl-ev" style={{ ["--a" as string]: accentFor(ev) }} onClick={(e) => { if (e.metaKey || e.ctrlKey || e.shiftKey) return; e.preventDefault(); setActive(ev); }} title={ev.title}>
                        {ev.start_time ? <span className="cl-ev-t">{ev.start_time}</span> : null}
                        <span className="cl-ev-x">{ev.title}</span>
                        {ev.location ? <span className="cl-ev-loc">{ev.location}</span> : null}
                      </a>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
          {dayCols.length === 0 && <div className="i-empty">No events{query ? " matching your search" : ""} right now.</div>}
        </>
      ) : (
        <>
          <div className="mg-nav">
            <button type="button" onClick={() => step(-1)} aria-label="Previous month">&lsaquo;</button>
            <span className="mg-month">{MONTHS[cursor.m]} {cursor.y}</span>
            <button type="button" onClick={() => step(1)} aria-label="Next month">&rsaquo;</button>
          </div>
          <div className="mg-wd">{WD.map((w) => <span key={w}>{w}</span>)}</div>
          <div className="mg-grid">
            {cells.map((c, i) => {
              if (!c) return <div key={`b${i}`} className="mg-cell mg-blank" />;
              const isToday = c.iso === todayIso;
              const isExp = expanded === c.iso;
              const shown = isExp ? c.events : c.events.slice(0, 3);
              const more = c.events.length - shown.length;
              return (
                <div key={c.iso} className={`mg-cell${isToday ? " mg-today" : ""}`}>
                  <div className="mg-date">{c.d}</div>
                  {shown.map((ev, k) => (
                    <a key={`${c.iso}-${k}`} href={citySlug && (ev as any).detailSlug ? `/${citySlug}/${(ev as any).detailSlug}` : undefined} className="mg-ev" style={{ ["--a" as string]: accentFor(ev) }} onClick={(e) => { if (e.metaKey || e.ctrlKey || e.shiftKey) return; e.preventDefault(); setActive(ev); }} title={ev.title}>
                      {ev.start_time ? <span className="mg-ev-t">{ev.start_time}</span> : null}
                      <span className="mg-ev-x">{ev.title}</span>
                    </a>
                  ))}
                  {more > 0 && (<button type="button" className="mg-more" onClick={() => setExpanded(c.iso)}>+{more} more</button>)}
                </div>
              );
            })}
          </div>
          {monthCount === 0 && (<div className="i-empty">Nothing in {MONTHS[cursor.m]}{query ? " matching your search" : ""}. Use the arrows to browse other months.</div>)}
        </>
      )}

      {srList}
      <EventModal event={active} onClose={() => setActive(null)} />

      <style>{`
        .iw { display: flex; flex-direction: column; gap: 14px; }
        .i-search { display: flex; align-items: center; gap: 12px; }
        .i-search input { flex: 1; padding: 12px 16px; font-size: 15px; font-family: inherit; border-radius: 12px; border: 1px solid rgba(255,255,255,0.18); background: rgba(255,255,255,0.06); color: #fff; outline: none; }
        .i-search input::placeholder { color: rgba(255,255,255,0.4); }
        .i-search input:focus { border-color: rgba(175,169,236,0.5); }
        .i-count { font-size: 12px; font-weight: 700; color: #AFA9EC; white-space: nowrap; }
        .i-empty { text-align: center; padding: 28px; color: rgba(255,255,255,0.5); font-size: 14px; }
        .i-sr { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0; }
        .mg-nav { display: flex; align-items: center; justify-content: center; gap: 18px; }
        .mg-nav button { width: 34px; height: 34px; border-radius: 50%; cursor: pointer; border: 1px solid rgba(255,255,255,0.18); background: rgba(255,255,255,0.06); color: #fff; font-size: 18px; line-height: 1; font-family: inherit; }
        .mg-nav button:hover { background: rgba(255,255,255,0.12); }
        .mg-month { font-family: 'DM Serif Display', serif; font-size: 22px; color: #fff; min-width: 210px; text-align: center; }
        .mg-wd { display: grid; grid-template-columns: repeat(7, 1fr); gap: 6px; }
        .mg-wd span { text-align: center; font-size: 11px; font-weight: 700; letter-spacing: 0.5px; text-transform: uppercase; color: rgba(255,255,255,0.5); }
        .mg-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 6px; }
        .mg-cell { min-height: 94px; border-radius: 10px; padding: 6px; background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); display: flex; flex-direction: column; gap: 3px; overflow: hidden; }
        .mg-blank { background: transparent; border: none; }
        .mg-today { border-color: rgba(175,169,236,0.55); background: rgba(127,119,221,0.12); }
        .mg-date { font-size: 12px; font-weight: 700; color: rgba(255,255,255,0.7); }
        .mg-today .mg-date { color: #fff; }
        .mg-ev { text-decoration: none; display: flex; flex-direction: column; align-items: flex-start; text-align: left; width: 100%; cursor: pointer; font-family: inherit; border: none; border-left: 3px solid var(--a); border-radius: 4px; background: color-mix(in srgb, var(--a) 22%, transparent); padding: 3px 6px; color: #fff; }
        .mg-ev:hover { background: color-mix(in srgb, var(--a) 40%, transparent); }
        .mg-ev-t { font-size: 9px; font-weight: 700; color: rgba(255,255,255,0.75); line-height: 1.1; }
        .mg-ev-x { font-size: 11px; font-weight: 600; line-height: 1.15; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 100%; }
        .mg-more { background: none; border: none; color: #AFA9EC; font-size: 10px; font-weight: 700; cursor: pointer; padding: 1px 4px; text-align: left; font-family: inherit; }
        .cl { display: grid; grid-template-columns: repeat(auto-fill, minmax(165px, 1fr)); gap: 10px; align-items: start; }
        .cl-col { background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; overflow: hidden; }
        .cl-head { padding: 8px 11px; background: rgba(127,119,221,0.15); border-bottom: 1px solid rgba(255,255,255,0.08); display: flex; flex-direction: column; gap: 1px; }
        .cl-wd { font-size: 10px; font-weight: 700; letter-spacing: 0.5px; text-transform: uppercase; color: rgba(255,255,255,0.55); }
        .cl-md { font-family: 'DM Serif Display', serif; font-size: 18px; color: #fff; line-height: 1; }
        .cl-evs { display: flex; flex-direction: column; gap: 6px; padding: 8px; }
        .cl-ev { text-decoration: none; display: flex; flex-direction: column; align-items: flex-start; text-align: left; width: 100%; cursor: pointer; font-family: inherit; border: none; border-left: 3px solid var(--a); border-radius: 6px; background: color-mix(in srgb, var(--a) 20%, transparent); padding: 6px 9px; color: #fff; }
        .cl-ev:hover { background: color-mix(in srgb, var(--a) 38%, transparent); }
        .cl-ev-t { font-size: 10px; font-weight: 700; color: rgba(255,255,255,0.75); }
        .cl-ev-x { font-size: 13px; font-weight: 600; line-height: 1.25; }
        .cl-ev-loc { font-size: 11px; color: rgba(255,255,255,0.55); margin-top: 2px; }
        @media (max-width: 700px) {
          .mg-grid, .mg-wd { gap: 3px; } .mg-cell { min-height: 72px; padding: 4px; } .mg-ev-x { font-size: 10px; } .mg-month { font-size: 18px; min-width: 150px; }
          .cl { grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); }
        }
      `}</style>
    </div>
  );
}
