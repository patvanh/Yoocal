"use client";

import { useMemo, useState } from "react";
import EventModal, { type EventModalData } from "@/components/EventModal";
import {
  TAG_LABELS,
  TAG_ORDER,
  type Venue,
  type VenueTag,
} from "@/lib/venues";

/**
 * Each venue arrives pre-paired with its matching events (computed
 * server-side from the JSON files). This component handles:
 *   - filter chips for venue tags
 *   - expand/collapse on individual venue cards
 *   - opening the EventModal when an event is clicked
 */

export type VenueWithEvents = {
  venue: Venue;
  events: EventModalData[];
};

export default function VenuesGrid({
  venues,
}: {
  venues: VenueWithEvents[];
}) {
  const [activeTag, setActiveTag] = useState<VenueTag | "all">("all");
  const [expandedVenue, setExpandedVenue] = useState<string | null>(null);
  const [openEvent, setOpenEvent] = useState<EventModalData | null>(null);

  // Tags that exist among the actual venues (don't show empty filter chips)
  const availableTags: VenueTag[] = useMemo(() => {
    const set = new Set<VenueTag>();
    for (const v of venues) {
      for (const tag of v.venue.tags) set.add(tag);
    }
    return TAG_ORDER.filter((t) => set.has(t));
  }, [venues]);

  const filteredVenues = useMemo(() => {
    if (activeTag === "all") return venues;
    return venues.filter((v) => v.venue.tags.includes(activeTag));
  }, [venues, activeTag]);

  return (
    <>
      <div className="filter-chips" role="tablist" aria-label="Venue categories">
        <button
          type="button"
          role="tab"
          aria-selected={activeTag === "all"}
          className={activeTag === "all" ? "chip active" : "chip"}
          onClick={() => setActiveTag("all")}
        >
          All venues
          <span className="chip-count">{venues.length}</span>
        </button>
        {availableTags.map((tag) => {
          const count = venues.filter((v) =>
            v.venue.tags.includes(tag),
          ).length;
          return (
            <button
              key={tag}
              type="button"
              role="tab"
              aria-selected={activeTag === tag}
              className={activeTag === tag ? "chip active" : "chip"}
              onClick={() => setActiveTag(tag)}
            >
              {TAG_LABELS[tag]}
              <span className="chip-count">{count}</span>
            </button>
          );
        })}
      </div>

      {filteredVenues.length === 0 ? (
        <div className="empty">
          No venues match this category. Try another filter.
        </div>
      ) : (
        <div className="venues-grid">
          {filteredVenues.map(({ venue, events }) => {
            const isExpanded = expandedVenue === venue.name;
            const upcoming = events.length;
            const previewEvents = events.slice(0, isExpanded ? events.length : 3);

            return (
              <article key={venue.name} className="venue-card">
                <header className="venue-head">
                  <div className="venue-emoji" aria-hidden="true">{venue.emoji}</div>
                  <div className="venue-text">
                    <h3>{venue.name}</h3>
                    <div className="venue-address">{venue.address}</div>
                    <div className="venue-tags">
                      {venue.tags.map((t) => (
                        <span key={t} className="venue-tag">{TAG_LABELS[t]}</span>
                      ))}
                    </div>
                  </div>
                </header>

                <p className="venue-desc">{venue.desc}</p>

                <div className="venue-events-head">
                  <span className="venue-events-count">
                    {upcoming === 0
                      ? "No upcoming events on file"
                      : `${upcoming} upcoming ${upcoming === 1 ? "event" : "events"}`}
                  </span>
                </div>

                {previewEvents.length > 0 && (
                  <ul className="venue-events">
                    {previewEvents.map((ev, i) => (
                      <li key={`${ev.title}-${ev.date}-${i}`}>
                        <button
                          type="button"
                          onClick={() => setOpenEvent(ev)}
                          className="venue-event-btn"
                        >
                          <span className="vev-date">
                            {formatShortDate(ev.date)}
                            {ev.start_time ? ` · ${ev.start_time}` : ""}
                          </span>
                          <span className="vev-title">{ev.title}</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}

                {events.length > 3 && (
                  <button
                    type="button"
                    className="venue-expand"
                    onClick={() =>
                      setExpandedVenue(isExpanded ? null : venue.name)
                    }
                  >
                    {isExpanded
                      ? "Show fewer events ↑"
                      : `Show all ${events.length} events ↓`}
                  </button>
                )}
              </article>
            );
          })}
        </div>
      )}

      <EventModal event={openEvent} onClose={() => setOpenEvent(null)} />

      <style>{`
        .filter-chips {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
          margin-bottom: 32px;
          padding: 6px;
          background: rgba(83,74,183,0.06);
          border-radius: 100px;
          width: fit-content;
          max-width: 100%;
        }
        .chip {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          background: transparent;
          border: none;
          color: var(--muted);
          font-size: 13px;
          font-weight: 600;
          padding: 8px 16px;
          border-radius: 100px;
          cursor: pointer;
          font-family: inherit;
          transition: all 0.15s;
          white-space: nowrap;
        }
        .chip:hover {
          color: var(--purple);
          background: rgba(255,255,255,0.5);
        }
        .chip.active {
          background: var(--purple);
          color: white;
        }
        .chip-count {
          background: rgba(255,255,255,0.18);
          color: inherit;
          font-size: 11px;
          padding: 2px 8px;
          border-radius: 100px;
          font-weight: 700;
        }
        .chip:not(.active) .chip-count {
          background: rgba(83,74,183,0.1);
          color: var(--purple);
        }

        .empty {
          text-align: center;
          padding: 60px 20px;
          color: var(--muted);
          background: white;
          border: 1px solid var(--border);
          border-radius: 16px;
        }

        .venues-grid {
          display: grid;
          gap: 20px;
          grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
        }
        .venue-card {
          background: white;
          border: 1px solid var(--border);
          border-radius: 20px;
          padding: 24px;
          display: flex;
          flex-direction: column;
          gap: 14px;
          transition: border-color 0.2s, box-shadow 0.2s;
        }
        .venue-card:hover {
          border-color: rgba(83,74,183,0.3);
          box-shadow: 0 8px 24px rgba(83,74,183,0.06);
        }

        .venue-head {
          display: flex;
          align-items: flex-start;
          gap: 14px;
        }
        .venue-emoji {
          font-size: 36px;
          line-height: 1;
          flex-shrink: 0;
        }
        .venue-text {
          flex: 1;
          min-width: 0;
        }
        .venue-text h3 {
          font-family: 'DM Serif Display', serif;
          font-size: 22px;
          margin: 0 0 4px;
          line-height: 1.15;
          color: var(--text);
        }
        .venue-address {
          font-size: 12px;
          color: var(--muted);
          margin-bottom: 8px;
        }
        .venue-tags {
          display: flex;
          gap: 6px;
          flex-wrap: wrap;
        }
        .venue-tag {
          font-size: 10px;
          font-weight: 700;
          letter-spacing: 0.4px;
          text-transform: uppercase;
          padding: 3px 9px;
          border-radius: 100px;
          background: rgba(83,74,183,0.08);
          color: var(--purple);
        }

        .venue-desc {
          font-size: 14px;
          color: var(--muted);
          line-height: 1.65;
          margin: 0;
        }

        .venue-events-head {
          padding-top: 10px;
          border-top: 1px solid var(--border);
        }
        .venue-events-count {
          font-size: 12px;
          font-weight: 700;
          letter-spacing: 0.3px;
          text-transform: uppercase;
          color: var(--amber);
        }

        .venue-events {
          list-style: none;
          padding: 0;
          margin: 0;
          display: grid;
          gap: 4px;
        }
        .venue-event-btn {
          display: grid;
          grid-template-columns: 110px 1fr;
          gap: 12px;
          align-items: center;
          width: 100%;
          padding: 8px 10px;
          border-radius: 8px;
          background: transparent;
          border: none;
          text-align: left;
          font-family: inherit;
          cursor: pointer;
          color: inherit;
          transition: background 0.12s;
        }
        .venue-event-btn:hover {
          background: rgba(83,74,183,0.05);
        }
        .vev-date {
          font-size: 11px;
          font-weight: 700;
          color: var(--purple);
          text-transform: uppercase;
          letter-spacing: 0.4px;
          font-variant-numeric: tabular-nums;
        }
        .vev-title {
          font-size: 14px;
          font-weight: 500;
          color: var(--text);
          line-height: 1.35;
        }

        .venue-expand {
          align-self: flex-start;
          background: transparent;
          border: none;
          color: var(--purple);
          font-size: 13px;
          font-weight: 600;
          cursor: pointer;
          padding: 4px 0;
          font-family: inherit;
        }
        .venue-expand:hover {
          text-decoration: underline;
        }

        @media (max-width: 520px) {
          .venues-grid { grid-template-columns: 1fr; }
          .venue-card { padding: 20px; }
          .venue-event-btn {
            grid-template-columns: 90px 1fr;
            gap: 8px;
            padding: 8px;
          }
          .vev-date { font-size: 10px; }
          .vev-title { font-size: 13px; }
        }
      `}</style>
    </>
  );
}

function formatShortDate(iso: string): string {
  const d = new Date(iso + "T12:00:00");
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}
