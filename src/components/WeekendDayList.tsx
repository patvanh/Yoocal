"use client";

import { useState } from "react";
import EventModal, { type EventModalData } from "@/components/EventModal";

/**
 * Client-side list of events for one day. Renders cards and owns the modal
 * state. Server component (/this-weekend/page.tsx) passes plain data in;
 * this component handles the click → modal interaction.
 */

export type WeekendDayEvent = EventModalData;

export default function WeekendDayList({ events }: { events: WeekendDayEvent[] }) {
  const [active, setActive] = useState<EventModalData | null>(null);

  return (
    <>
      <ul className="event-list">
        {events.map((ev, i) => {
          const tag = priceTag(ev);
          return (
            <li key={`${ev.title}-${ev.start_time ?? "any"}-${i}`}>
              <button
                type="button"
                onClick={() => setActive(ev)}
                className="event-card"
              >
                <div className="event-time">
                  {ev.start_time ?? "All day"}
                  {ev.end_time && ev.start_time ? ` – ${ev.end_time}` : ""}
                </div>
                <div className="event-body">
                  <h3>{ev.title}</h3>
                  {ev.location && (
                    <div className="event-location">{ev.location}</div>
                  )}
                  {ev.description && (
                    <p className="event-desc">
                      {truncate(ev.description, 180)}
                    </p>
                  )}
                  <div className="event-meta">
                    {tag && <span className="event-tag free">{tag}</span>}
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
        .event-list {
          list-style: none;
          padding: 0;
          margin: 0;
          display: grid;
          gap: 12px;
        }
        .event-list .event-card {
          display: grid;
          grid-template-columns: 110px 1fr;
          gap: 24px;
          padding: 20px 22px;
          background: white;
          border: 1px solid var(--border);
          border-radius: 16px;
          text-align: left;
          color: inherit;
          font-family: inherit;
          cursor: pointer;
          width: 100%;
          transition: all 0.18s;
        }
        .event-list .event-card:hover {
          border-color: var(--purple);
          transform: translateY(-2px);
          box-shadow: 0 8px 24px rgba(83,74,183,0.08);
        }
        .event-time {
          font-size: 13px;
          font-weight: 700;
          color: var(--purple);
          text-transform: uppercase;
          letter-spacing: 0.5px;
          padding-top: 3px;
          font-variant-numeric: tabular-nums;
        }
        .event-body { min-width: 0; }
        .event-body h3 {
          font-size: 17px;
          font-weight: 600;
          margin: 0 0 4px;
          line-height: 1.3;
        }
        .event-location {
          font-size: 13px;
          color: var(--muted);
          margin-bottom: 6px;
        }
        .event-desc {
          font-size: 14px;
          color: var(--muted);
          line-height: 1.6;
          margin: 6px 0 10px;
        }
        .event-meta {
          display: flex;
          align-items: center;
          gap: 10px;
          flex-wrap: wrap;
          font-size: 12px;
        }
        .event-tag {
          padding: 3px 10px;
          border-radius: 100px;
          font-weight: 700;
          letter-spacing: 0.3px;
          text-transform: uppercase;
        }
        .event-tag.free {
          background: rgba(239,159,39,0.15);
          color: #b67200;
        }
        .event-source {
          color: var(--muted);
          font-style: italic;
        }
        .event-link {
          margin-left: auto;
          color: var(--purple);
          font-weight: 600;
        }

        @media (max-width: 600px) {
          .event-list .event-card {
            grid-template-columns: 1fr;
            gap: 4px;
            padding: 16px;
          }
          .event-time { font-size: 12px; }
          .event-meta { font-size: 11px; gap: 8px; }
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
