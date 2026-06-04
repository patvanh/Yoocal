"use client";

import { useState } from "react";
import EventModal, { type EventModalData } from "@/components/EventModal";

const CAT_COLOR: Record<string, string> = {
  "Music": "#7c5cff",
  "Arts & Theater": "#d6457a",
  "Food & Drink": "#e0892a",
  "Outdoors": "#2fa36b",
  "Running & Races": "#e0892a",
  "Sports": "#2f7fa3",
  "Family & Kids": "#c0489b",
  "Wellness": "#3aa39a",
  "Nightlife": "#9b51e0",
  "Education & Talks": "#5566c4",
  "Community": "#6b61d6",
};

function accentFor(ev: EventModalData): string {
  for (const c of ev.categories || []) {
    if (CAT_COLOR[c]) return CAT_COLOR[c];
  }
  return "#6b61d6";
}

function dayLabel(iso: string): { weekday: string; rest: string } {
  // iso "YYYY-MM-DD" -> parse as local date (avoid TZ shift)
  const [y, m, d] = iso.split("-").map((n) => parseInt(n, 10));
  const dt = new Date(y, (m || 1) - 1, d || 1);
  const weekday = dt.toLocaleDateString("en-US", { weekday: "long" });
  const rest = dt.toLocaleDateString("en-US", { month: "long", day: "numeric" });
  return { weekday, rest };
}

export default function IntentDayList({ events }: { events: EventModalData[] }) {
  const [active, setActive] = useState<EventModalData | null>(null);

  // Group by start date (YYYY-MM-DD), preserving the incoming sort order.
  const groups: { iso: string; events: EventModalData[] }[] = [];
  for (const ev of events) {
    const iso = (ev.date || "").slice(0, 10);
    if (!iso) continue;
    let g = groups.find((x) => x.iso === iso);
    if (!g) { g = { iso, events: [] }; groups.push(g); }
    g.events.push(ev);
  }

  return (
    <>
      <div className="ip-days">
        {groups.map((g) => {
          const { weekday, rest } = dayLabel(g.iso);
          return (
            <section key={g.iso} className="ip-day">
              <div className="ip-day-head">
                <span className="ip-day-weekday">{weekday}</span>
                <span className="ip-day-date">{rest}</span>
                <span className="ip-day-count">{g.events.length} {g.events.length === 1 ? "event" : "events"}</span>
              </div>
              <ul className="ip-list">
                {g.events.map((ev, i) => {
                  const accent = accentFor(ev);
                  const cat = (ev.categories || [])[0];
                  const tag = priceTag(ev);
                  return (
                    <li key={`${ev.title}-${ev.start_time ?? "any"}-${i}`}>
                      <button
                        type="button"
                        onClick={() => setActive(ev)}
                        className="ip-card"
                        style={{ ["--accent" as string]: accent }}
                      >
                        <div className="ip-time">
                          <span className="ip-time-main">{ev.start_time ?? "All day"}</span>
                          {ev.end_time && ev.start_time ? (
                            <span className="ip-time-end">until {ev.end_time}</span>
                          ) : null}
                        </div>
                        <div className="ip-cardbody">
                          <h3>{ev.title}</h3>
                          {ev.location && <div className="ip-loc">{ev.location}</div>}
                          {ev.description && <p className="ip-desc">{truncate(ev.description, 150)}</p>}
                          <div className="ip-meta">
                            {cat && <span className="ip-cat">{cat}</span>}
                            {tag && <span className={`ip-tag${tag === "Free" ? " free" : ""}`}>{tag}</span>}
                            {ev.source && <span className="ip-src">via {ev.source}</span>}
                            <span className="ip-link">Details →</span>
                          </div>
                        </div>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </section>
          );
        })}
      </div>

      <EventModal event={active} onClose={() => setActive(null)} />

      <style>{`
        .ip-days { display: flex; flex-direction: column; gap: 36px; }
        .ip-day-head {
          display: flex; align-items: baseline; gap: 12px;
          padding: 0 4px 14px; margin-bottom: 4px;
          border-bottom: 2px solid rgba(26,24,48,0.10);
        }
        .ip-day-weekday {
          font-family: 'DM Serif Display', serif; font-size: 24px; color: #16142b; line-height: 1;
        }
        .ip-day-date { font-size: 15px; color: #8b88a0; font-weight: 600; }
        .ip-day-count {
          margin-left: auto; font-size: 11px; font-weight: 700; letter-spacing: 0.5px;
          text-transform: uppercase; color: #6b61d6;
          background: rgba(107,97,214,0.10); padding: 4px 11px; border-radius: 100px;
        }
        .ip-list { list-style: none; padding: 0; margin: 0; display: grid; gap: 12px; }
        .ip-card {
          position: relative; display: grid; grid-template-columns: 104px 1fr; gap: 20px;
          padding: 20px 22px 20px 24px; background: #fff;
          border: 1px solid rgba(26,24,48,0.06); border-left: 5px solid var(--accent);
          border-radius: 16px; text-align: left; color: #1a1830; font-family: inherit;
          cursor: pointer; width: 100%; box-shadow: 0 3px 12px rgba(26,24,48,0.05);
          transition: transform 0.16s ease, box-shadow 0.16s ease;
        }
        .ip-card:hover { transform: translateY(-3px); box-shadow: 0 16px 36px rgba(26,24,48,0.16); }
        .ip-time { display: flex; flex-direction: column; gap: 2px; padding-top: 2px; font-variant-numeric: tabular-nums; }
        .ip-time-main { font-size: 14px; font-weight: 800; color: var(--accent); line-height: 1.15; }
        .ip-time-end { font-size: 12px; color: #9b98ac; font-weight: 500; }
        .ip-cardbody { min-width: 0; }
        .ip-cardbody h3 { font-family: 'DM Serif Display', serif; font-size: 19px; font-weight: 400; margin: 0 0 5px; line-height: 1.22; color: #16142b; }
        .ip-loc { font-size: 13px; color: #8b88a0; margin-bottom: 7px; font-weight: 500; }
        .ip-desc { font-size: 14px; color: #565270; line-height: 1.55; margin: 7px 0 12px; }
        .ip-meta { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font-size: 12px; }
        .ip-cat {
          padding: 3px 11px; border-radius: 100px; font-weight: 700; font-size: 11px;
          letter-spacing: 0.3px; text-transform: uppercase;
          background: color-mix(in srgb, var(--accent) 13%, white); color: var(--accent);
        }
        .ip-tag {
          padding: 3px 11px; border-radius: 100px; font-weight: 700; font-size: 11px;
          letter-spacing: 0.3px; text-transform: uppercase;
          background: rgba(26,24,48,0.06); color: #565270;
        }
        .ip-tag.free { background: rgba(47,163,107,0.15); color: #1f8a52; }
        .ip-src { color: #a4a1b5; font-style: italic; }
        .ip-link { margin-left: auto; color: var(--accent); font-weight: 700; }
        @media (max-width: 600px) {
          .ip-card { grid-template-columns: 1fr; gap: 6px; padding: 16px 16px 16px 18px; }
          .ip-time { flex-direction: row; gap: 8px; align-items: baseline; }
          .ip-cardbody h3 { font-size: 17px; }
          .ip-link { margin-left: 0; }
          .ip-day-weekday { font-size: 20px; }
        }
      `}</style>
    </>
  );
}

function priceTag(ev: EventModalData): string | null {
  if (ev.is_free === true) return "Free";
  if (ev.price && ev.price.trim()) return ev.price;
  return null;
}

function truncate(s: string, max: number): string {
  if (s.length <= max) return s;
  return s.slice(0, max).replace(/\s+\S*$/, "") + "…";
}
