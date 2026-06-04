"use client";

import { useState } from "react";
import EventModal, { type EventModalData } from "@/components/EventModal";

export type WeekendDayEvent = EventModalData;

// Map a category bucket to an accent hue. First matchingcategory wins.
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

export default function WeekendDayList({ events }: { events: WeekendDayEvent[] }) {
  const [active, setActive] = useState<EventModalData | null>(null);

  return (
    <>
      <ul className="event-list">
        {events.map((ev, i) => {
          const tag = priceTag(ev);
          const accent = accentFor(ev);
          const cat = (ev.categories || [])[0];
          return (
            <li key={`${ev.title}-${ev.start_time ?? "any"}-${i}`}>
              <button
                type="button"
                onClick={() => setActive(ev)}
                className="event-card"
                style={{ ["--accent" as string]: accent }}
              >
                <div className="event-time">
                  <span className="event-time-main">{ev.start_time ?? "All day"}</span>
                  {ev.end_time && ev.start_time ? (
                    <span className="event-time-end">until {ev.end_time}</span>
                  ) : null}
                </div>
                <div className="event-body">
                  <h3>{ev.title}</h3>
                  {ev.location && (
                    <div className="event-location">{ev.location}</div>
                  )}
                  {ev.description && (
                    <p className="event-desc">
                      {truncate(ev.description, 160)}
                    </p>
                  )}
                  <div className="event-meta">
                    {cat && <span className="event-cat">{cat}</span>}
                    {tag && <span className={`event-tag${tag === "Free" ? " free" : ""}`}>{tag}</span>}
                    {ev.source && (
                      <span className="event-source">via {ev.source}</span>
                    )}
                    <span className="event-link">Details →</span>
                  </div>
                </div>
              </button>
            </li>
          );
        })}
      </ul>

      <EventModal event={active} onClose={() => setActive(null)} />

      <style>{`
        .event-list { list-style: none; padding: 0; margin: 0; display: grid; gap: 14px; }
        .event-list .event-card {
          position: relative;
          display: grid;
          grid-template-columns: 116px 1fr;
          gap: 22px;
          padding: 22px 24px 22px 28px;
          background: #ffffff;
          border: 1px solid rgba(26,24,48,0.07);
          border-left: 4px solid var(--accent);
          border-radius: 18px;
          text-align: left;
          color: #1a1830;
          font-family: inherit;
          cursor: pointer;
          width: 100%;
          box-shadow: 0 2px 8px rgba(26,24,48,0.04);
          transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
        }
        .event-list .event-card:hover {
          transform: translateY(-3px);
          box-shadow: 0 14px 32px rgba(26,24,48,0.14);
        }
        .event-time {
          display: flex; flex-direction: column; gap: 2px;
          padding-top: 3px;
          font-variant-numeric: tabular-nums;
        }
        .event-time-main {
          font-size: 15px; font-weight: 800; color: var(--accent);
          letter-spacing: -0.2px; line-height: 1.15;
        }
        .event-time-end { font-size: 12px; color: #8b88a0; font-weight: 500; }
        .event-body { min-width: 0; }
        .event-body h3 {
          font-family: 'DM Serif Display', serif;
          font-size: 20px; font-weight: 400; margin: 0 0 5px; line-height: 1.2;
          color: #16142b;
        }
        .event-location { font-size: 13px; color: #8b88a0; margin-bottom: 8px; font-weight: 500; }
        .event-desc { font-size: 14px; color: #565270; line-height: 1.6; margin: 8px 0 14px; }
        .event-meta { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font-size: 12px; }
        .event-cat {
          padding: 3px 11px; border-radius: 100px; font-weight: 700;
          font-size: 11px; letter-spacing: 0.3px; text-transform: uppercase;
          background: color-mix(in srgb, var(--accent) 14%, white);
          color: var(--accent);
        }
        .event-tag {
          padding: 3px 11px; border-radius: 100px; font-weight: 700;
          font-size: 11px; letter-spacing: 0.3px; text-transform: uppercase;
          background: rgba(26,24,48,0.06); color: #565270;
        }
        .event-tag.free { background: rgba(47,163,107,0.15); color: #1f8a52; }
        .event-source { color: #a4a1b5; font-style: italic; }
        .event-link { margin-left: auto; color: var(--accent); font-weight: 700; }
        @media (max-width: 600px) {
          .event-list .event-card { grid-template-columns: 1fr; gap: 8px; padding: 18px 18px 18px 20px; }
          .event-time { flex-direction: row; gap: 8px; align-items: baseline; }
          .event-body h3 { font-size: 18px; }
          .event-link { margin-left: 0; }
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
