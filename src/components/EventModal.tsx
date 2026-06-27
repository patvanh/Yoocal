"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Reusable event modal — matches the existing yoocal.com modal design.
 *
 * Usage pattern:
 *   const [openEvent, setOpenEvent] = useState<EventModalData | null>(null);
 *   ...
 *   <button onClick={() => setOpenEvent({ title, date, ... })}>card</button>
 *   <EventModal event={openEvent} onClose={() => setOpenEvent(null)} />
 *
 * Three actions: View full details (opens source URL), Add to calendar
 * (Google/Apple/Outlook dropdown), Share (copy link / Twitter / Facebook).
 */

// Map a link's domain to a clean source label, so the "via" credit matches
// where the link actually goes. Many aggregator sources (e.g. The Park Record)
// republish events that link out to the true origin (library, venue, presenter);
// showing "via The Park Record" while the link went to nowplayingutah.com was
// misleading. We credit the real destination instead, falling back to the
// scrape source for social/unknown domains (a raw instagram.com link is an odd
// "source").
const VIA_SOURCE_LABELS: Record<string, string> = {
  'utaholympiclegacy.org': 'Utah Olympic Park',
  'mountaintownmusic.org': 'Mountain Town Music',
  'parkcity.events.mylibrary.digital': 'Park City Library',
  'summit.events.mylibrary.digital': 'Summit County Library',
  'altacommunity.org': 'Alta Community',
  'tockify.com': 'Park City Calendar',
  'bandsintown.com': 'Bandsintown',
  'eventbrite.com': 'Eventbrite',
  'parkcity.org': 'Visit Park City',
  'swanerecocenter.org': 'Swaner EcoCenter',
};
const VIA_SOCIAL_DOMAINS = new Set([
  'instagram.com', 'facebook.com', 'twitter.com', 'x.com', 'tiktok.com',
]);

function viaLabelFor(event: { link?: string; source?: string }): string {
  const link = (event.link || '').trim();
  let dom = '';
  try { dom = new URL(link).hostname.replace(/^www\./, ''); } catch { return event.source || ''; }
  if (!dom || VIA_SOCIAL_DOMAINS.has(dom)) return event.source || dom;
  return VIA_SOURCE_LABELS[dom] || event.source || dom;
}

export type EventModalData = {
  title: string;
  date: string;             // ISO "YYYY-MM-DD"
  end_date?: string;        // ISO "YYYY-MM-DD" for multi-day events
  start_time?: string;      // "11:00 AM"
  end_time?: string;
  location?: string;
  description?: string;
  link?: string;            // source URL
  source?: string;          // "Heber Valley Tourism"
  is_free?: boolean | null;
  price?: string;
  categories?: string[];    // ["Outdoor", "Music"]
  image_url?: string;
};

export default function EventModal({
  event,
  onClose,
}: {
  event: EventModalData | null;
  onClose: () => void;
}) {
  const [showCalDropdown, setShowCalDropdown] = useState(false);
  const [showShareDropdown, setShowShareDropdown] = useState(false);
  const [copied, setCopied] = useState(false);
  const [descExpanded, setDescExpanded] = useState(false);
  const [descClamped, setDescClamped] = useState(false);
  const descRef = useRef<HTMLParagraphElement | null>(null);

  useEffect(() => {
    setDescExpanded(false);
    // Measure after paint: is the (unclamped) text taller than the clamp box?
    const id = requestAnimationFrame(() => {
      const el = descRef.current;
      if (el) setDescClamped(el.scrollHeight - el.clientHeight > 4);
    });
    return () => cancelAnimationFrame(id);
  }, [event?.title, event?.description]);
  const modalRef = useRef<HTMLDivElement | null>(null);

  // Close on Escape, lock body scroll while open
  useEffect(() => {
    if (!event) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [event, onClose]);

  // Reset dropdowns/copied state when event changes
  useEffect(() => {
    setShowCalDropdown(false);
    setShowShareDropdown(false);
    setCopied(false);
  }, [event]);

  if (!event) return null;

  const dateLabel = formatDateRange(event.date, event.end_date);
  const tag = priceTag(event);

  const sourceUrl = event.link?.trim() ? event.link : null;
  const calLinks = buildCalendarLinks(event);
  const shareUrl = sourceUrl ?? "https://www.yoocal.com";
  const shareText = `${event.title} — ${dateLabel}${event.location ? " · " + event.location : ""}`;

  async function copyShareLink() {
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      // browsers without clipboard API — fall through silently
    }
  }

  return (
    <>
      <div
        className="ye-overlay"
        onClick={onClose}
        aria-hidden="true"
      />
      <div
        ref={modalRef}
        className="ye-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="ye-modal-title"
      >
        {event.image_url && /^https?:\/\//.test(event.image_url) && (
          <div
            aria-hidden="true"
            className="ye-img"
            style={{
              background: `center/cover no-repeat url(${event.image_url})`,
            }}
          />
        )}
        <div className="ye-modal-head">
          <div className="ye-tags">
            {event.categories?.map((c) => (
              <span key={c} className="ye-tag">{c}</span>
            ))}
            {tag && <span className="ye-tag free">{tag}</span>}
          </div>
          <button
            type="button"
            className="ye-close"
            onClick={onClose}
            aria-label="Close"
          >
            ×
          </button>
        </div>

        {event.title && event.title.trim() && (
          <h2 id="ye-modal-title" className="ye-title">{event.title}</h2>
        )}

        <div className="ye-meta">
          <div className="ye-meta-row">
            <span className="ye-meta-icon" aria-hidden="true">📅</span>
            <span>{dateLabel}</span>
          </div>
          {event.start_time && (
            <div className="ye-meta-row">
              <span className="ye-meta-icon" aria-hidden="true">🕐</span>
              <span>
                {event.start_time}
                {event.end_time ? ` – ${event.end_time}` : ""}
              </span>
            </div>
          )}
          {event.location && (
            <div className="ye-meta-row">
              <span className="ye-meta-icon" aria-hidden="true">📍</span>
              <span>{event.location}</span>
            </div>
          )}
          {event.source && (
            <div className="ye-meta-row muted">
              <span className="ye-meta-icon" aria-hidden="true">🔗</span>
              <span>via {viaLabelFor(event)}</span>
            </div>
          )}
        </div>

        {event.description && (
          <div className="ye-desc-wrap">
            <p
              ref={descRef}
              className={`ye-desc${descExpanded ? " expanded" : ""}`}
            >
              {event.description}
            </p>
            {descClamped && (
              <button
                type="button"
                className="ye-desc-toggle"
                onClick={() => setDescExpanded((v) => !v)}
              >
                {descExpanded ? "See less" : "See more"}
              </button>
            )}
          </div>
        )}

        <div className="ye-actions">
          {sourceUrl && (
            <a
              href={sourceUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="ye-btn primary"
            >
              View full details ↗
            </a>
          )}

          <div className="ye-btn-wrap">
            <button
              type="button"
              className="ye-btn"
              onClick={() => {
                setShowCalDropdown((v) => !v);
                setShowShareDropdown(false);
              }}
              aria-expanded={showCalDropdown}
            >
              📅 Add to calendar
            </button>
            {showCalDropdown && (
              <div className="ye-dd" role="menu">
                <a href={calLinks.google} target="_blank" rel="noopener noreferrer">Google Calendar</a>
                <a href={calLinks.outlook} target="_blank" rel="noopener noreferrer">Outlook</a>
                <a href={calLinks.ics} download={`${slugify(event.title)}.ics`}>Apple / .ics file</a>
              </div>
            )}
          </div>

          <div className="ye-btn-wrap">
            <button
              type="button"
              className="ye-btn"
              onClick={() => {
                setShowShareDropdown((v) => !v);
                setShowCalDropdown(false);
              }}
              aria-expanded={showShareDropdown}
            >
              ↗ Share
            </button>
            {showShareDropdown && (
              <div className="ye-dd" role="menu">
                <button type="button" onClick={copyShareLink}>
                  {copied ? "✓ Copied!" : "Copy link"}
                </button>
                <a
                  href={`https://twitter.com/intent/tweet?text=${encodeURIComponent(shareText)}&url=${encodeURIComponent(shareUrl)}`}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Twitter / X
                </a>
                <a
                  href={`https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(shareUrl)}`}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Facebook
                </a>
                <a
                  href={`mailto:?subject=${encodeURIComponent(event.title)}&body=${encodeURIComponent(shareText + "\n\n" + shareUrl)}`}
                >
                  Email
                </a>
              </div>
            )}
          </div>
        </div>
      </div>

      <style>{`
        .ye-overlay {
          position: fixed; inset: 0;
          background: rgba(10,8,30,0.75);
          backdrop-filter: blur(4px);
          -webkit-backdrop-filter: blur(4px);
          z-index: 10000;
          animation: ye-fade 0.18s ease-out;
        }
        .ye-modal {
          position: fixed;
          top: 50%; left: 50%;
          transform: translate(-50%,-50%);
          z-index: 10001;
          width: min(560px, 92vw);
          max-height: 85vh; overflow-y: auto; overflow-x: visible;
          background: #1e1b3a;
          border-radius: 20px;
          border: 2px solid #7c5cff;
          box-shadow: 0 24px 80px rgba(0,0,0,0.5);
          padding: 28px 28px 24px;
          color: white;
          animation: ye-pop 0.2s ease-out;
        }
        @media (max-width: 640px) {
          .ye-modal {
            width: min(400px, 88vw);
            height: 42dvh;
            max-height: 42dvh;
            overflow: hidden;
            border-radius: 18px;
            padding: 22px 20px calc(20px + env(safe-area-inset-bottom));
            -webkit-overflow-scrolling: touch;
          }
          .ye-modal .ye-modal-head {
            position: sticky;
            top: 0;
            background: #1e1b3a;
            padding-top: 4px;
            margin: -4px -2px 2px;
            padding-bottom: 6px;
            z-index: 2;
          }
          .ye-modal .ye-img {
            margin: -22px -20px 16px;
            height: 110px;
            border-radius: 18px 18px 0 0;
          }
          .ye-modal .ye-title { margin: 0 0 6px; font-size: 15px; }
          .ye-modal .ye-meta { margin-bottom: 8px; gap: 3px; }
          .ye-modal .ye-meta-row { font-size: 13px; line-height: 1.3; }
          .ye-modal .ye-meta-row.muted { font-size: 11px; }
          .ye-modal .ye-desc-wrap { display: none; }
          .ye-modal .ye-desc { -webkit-line-clamp: 2; }
          .ye-modal .ye-actions { gap: 8px; flex-direction: row; flex-wrap: wrap; }
          .ye-modal .ye-actions > .ye-btn.primary { flex: 1 1 100%; }
          .ye-modal .ye-actions .ye-btn-wrap { flex: 1 1 0; min-width: 0; }
          .ye-modal .ye-actions .ye-btn-wrap .ye-btn { width: 100%; }
          .ye-modal .ye-actions .ye-btn.primary { flex: 1 1 100%; }
          .ye-modal .ye-actions .ye-btn-wrap { flex: 1 1 0; }
          .ye-modal .ye-actions .ye-btn-wrap .ye-btn { width: 100%; }
          .ye-modal .ye-btn { padding: 9px 16px; font-size: 13px; }
          .ye-modal .ye-tag { font-size: 10px; padding: 3px 9px; }
        }
        @keyframes ye-fade {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @keyframes ye-pop {
          from { opacity: 0; transform: translate(-50%,-48%) scale(0.96); }
          to { opacity: 1; transform: translate(-50%,-50%) scale(1); }
        }

        .ye-modal-head {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 14px;
          margin-bottom: 14px;
        }
        .ye-tags {
          display: flex; gap: 6px; flex-wrap: wrap;
        }
        .ye-tag {
          font-size: 11px;
          font-weight: 600;
          padding: 4px 10px;
          border-radius: 100px;
          background: rgba(255,255,255,0.1);
          color: rgba(255,255,255,0.85);
          letter-spacing: 0.3px;
        }
        .ye-tag.free {
          background: rgba(239,159,39,0.18);
          color: #f6c374;
        }

        .ye-close {
          background: rgba(255,255,255,0.08);
          border: none; color: rgba(255,255,255,0.7);
          width: 40px; height: 40px;
          border-radius: 50%;
          cursor: pointer; font-size: 24px;
          flex-shrink: 0;
          display: flex; align-items: center; justify-content: center;
          line-height: 1;
          padding: 0;
          -webkit-tap-highlight-color: transparent;
          touch-action: manipulation;
        }
        .ye-close:hover {
          background: rgba(255,255,255,0.16);
          color: white;
        }
        .ye-close:active {
          background: rgba(255,255,255,0.22);
        }
        @media (max-width: 600px) {
          .ye-close {
            width: 48px; height: 48px;
            font-size: 28px;
            background: rgba(255,255,255,0.12);
          }
        }

        .ye-img {
          margin: -28px -28px 20px;
          height: 200px;
          border-radius: 20px 20px 0 0;
        }
        .ye-modal .ye-title {
          font-family: 'DM Serif Display', serif;
          font-size: clamp(22px, 4vw, 30px);
          color: #fff;
          line-height: 1.2;
          margin: 0 0 18px;
        }

        .ye-meta {
          display: flex;
          flex-direction: column;
          gap: 10px;
          margin-bottom: 20px;
        }
        .ye-meta-row {
          display: flex;
          align-items: flex-start;
          gap: 10px;
          font-size: 15px;
          color: rgba(255,255,255,0.85);
          line-height: 1.5;
        }
        .ye-meta-row.muted {
          color: rgba(255,255,255,0.5);
          font-size: 13px;
        }
        .ye-meta-icon {
          flex-shrink: 0;
          font-size: 16px;
          width: 20px;
          text-align: center;
        }

        .ye-desc-wrap { margin: 0 0 24px; }
        .ye-desc {
          font-size: 15px;
          color: rgba(255,255,255,0.6);
          line-height: 1.7;
          margin: 0;
          display: -webkit-box;
          -webkit-box-orient: vertical;
          -webkit-line-clamp: 4;
          overflow: hidden;
        }
        .ye-desc.expanded {
          -webkit-line-clamp: unset;
          overflow: visible;
        }
        .ye-desc-toggle {
          margin-top: 8px;
          background: none;
          border: none;
          padding: 0;
          color: #9b8ff0;
          font-size: 14px;
          font-weight: 600;
          cursor: pointer;
          font-family: inherit;
        }
        .ye-desc-toggle:hover { text-decoration: underline; }

        .ye-actions {
          display: flex;
          gap: 10px;
          flex-wrap: wrap;
        }
        .ye-btn-wrap { position: relative; }
        .ye-dd-up { transform-origin: bottom left; }
        .ye-btn {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          background: rgba(255,255,255,0.08);
          border: 1px solid rgba(255,255,255,0.12);
          color: white;
          padding: 11px 20px;
          border-radius: 100px;
          font-size: 14px;
          font-weight: 600;
          cursor: pointer;
          text-decoration: none;
          font-family: inherit;
          transition: background 0.15s;
        }
        .ye-btn:hover {
          background: rgba(255,255,255,0.14);
        }
        .ye-btn.primary {
          background: #534AB7;
          border-color: #534AB7;
        }
        .ye-btn.primary:hover {
          background: #6961c9;
        }

        .ye-dd { position: absolute; bottom: calc(100% + 6px); left: 0;
          background: #2a2552;
          border: 1px solid rgba(255,255,255,0.12);
          border-radius: 12px;
          padding: 6px;
          min-width: 180px;
          box-shadow: 0 12px 32px rgba(0,0,0,0.4);
          z-index: 10;
        }
        .ye-dd a, .ye-dd button {
          display: block;
          width: 100%;
          text-align: left;
          padding: 8px 12px;
          font-size: 14px;
          color: rgba(255,255,255,0.85);
          background: none;
          border: none;
          border-radius: 6px;
          text-decoration: none;
          cursor: pointer;
          font-family: inherit;
        }
        .ye-dd a:hover, .ye-dd button:hover {
          background: rgba(255,255,255,0.08);
          color: white;
        }

        @media (max-width: 520px) {
          .ye-title {
            font-size: 22px;
          }
          .ye-actions {
            flex-direction: row;
            flex-wrap: wrap;
          }
          .ye-btn { width: 100%; justify-content: center; }
          .ye-actions > .ye-btn.primary { flex: 1 1 100%; }
          .ye-btn-wrap { flex: 1 1 0; min-width: 0; }
          .ye-btn-wrap .ye-btn { width: 100%; }
          .ye-dd { left: 0; right: 0; bottom: calc(100% + 6px); }
        }
      `}</style>
    </>
  );
}

/* ---------- helpers ---------- */

function priceTag(ev: EventModalData): string | null {
  if (ev.is_free === true) return "Free";
  if (ev.price && ev.price.trim()) return ev.price;
  return null;
}

function formatDateRange(start: string, end?: string): string {
  const s = formatLongDate(start);
  if (!end || end === start) return s;
  return `${s} – ${formatLongDate(end)}`;
}

function formatLongDate(iso: string): string {
  const d = new Date(iso + "T12:00:00"); // noon to dodge TZ shifts
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}

function slugify(s: string): string {
  return s
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60);
}

function buildCalendarLinks(ev: EventModalData) {
  const dt = formatCalendarDateRange(ev);
  const title = encodeURIComponent(ev.title);
  const details = encodeURIComponent(
    [ev.description, ev.link ? `\nSource: ${ev.link}` : ""].filter(Boolean).join("\n"),
  );
  const loc = encodeURIComponent(ev.location ?? "");

  const google =
    `https://www.google.com/calendar/render?action=TEMPLATE` +
    `&text=${title}&dates=${dt.googleRange}` +
    `&details=${details}&location=${loc}`;

  const outlook =
    `https://outlook.live.com/calendar/0/deeplink/compose?path=/calendar/action/compose&rru=addevent` +
    `&subject=${title}&startdt=${dt.outlookStart}&enddt=${dt.outlookEnd}` +
    `&body=${details}&location=${loc}`;

  const ics = buildIcsDataUri(ev, dt);

  return { google, outlook, ics };
}

function formatCalendarDateRange(ev: EventModalData) {
  // Parse start
  const startDate = ev.date;
  const endDate = ev.end_date || ev.date;
  const startTime = parse12hTime(ev.start_time);
  const endTime = parse12hTime(ev.end_time);

  if (startTime) {
    const startStr = `${stripDashes(startDate)}T${startTime}00`;
    const endStr = endTime
      ? `${stripDashes(endDate)}T${endTime}00`
      : `${stripDashes(endDate)}T${addOneHour(startTime)}00`;
    return {
      googleRange: `${startStr}/${endStr}`,
      outlookStart: toIsoLocal(startDate, startTime),
      outlookEnd: toIsoLocal(endDate, endTime ?? addOneHour(startTime)),
      isAllDay: false,
      startStr,
      endStr,
    };
  }

  // All-day
  const startStr = stripDashes(startDate);
  // Google all-day end is exclusive — add 1 day
  const endStr = stripDashes(addDays(endDate, 1));
  return {
    googleRange: `${startStr}/${endStr}`,
    outlookStart: `${startDate}T00:00:00`,
    outlookEnd: `${endDate}T23:59:00`,
    isAllDay: true,
    startStr,
    endStr,
  };
}

function parse12hTime(t?: string): string | null {
  if (!t) return null;
  const m = t.trim().match(/^(\d{1,2}):(\d{2})\s*(AM|PM)?$/i);
  if (!m) return null;
  let hour = parseInt(m[1], 10);
  const min = m[2];
  const ampm = m[3]?.toUpperCase();
  if (ampm === "PM" && hour !== 12) hour += 12;
  if (ampm === "AM" && hour === 12) hour = 0;
  return `${String(hour).padStart(2, "0")}${min}`;
}

function addOneHour(time: string): string {
  // time like "1900"
  const h = parseInt(time.slice(0, 2), 10);
  const m = time.slice(2);
  const nh = (h + 1) % 24;
  return `${String(nh).padStart(2, "0")}${m}`;
}

function stripDashes(iso: string): string {
  return iso.replace(/-/g, "");
}

function toIsoLocal(date: string, hhmm: string): string {
  const hh = hhmm.slice(0, 2);
  const mm = hhmm.slice(2, 4);
  return `${date}T${hh}:${mm}:00`;
}

function addDays(iso: string, days: number): string {
  const d = new Date(iso + "T12:00:00");
  d.setDate(d.getDate() + days);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function buildIcsDataUri(ev: EventModalData, dt: ReturnType<typeof formatCalendarDateRange>): string {
  const lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//Yoocal//Event//EN",
    "BEGIN:VEVENT",
    `UID:${slugify(ev.title)}-${dt.startStr}@yoocal.com`,
    `SUMMARY:${escIcs(ev.title)}`,
  ];
  if (dt.isAllDay) {
    lines.push(`DTSTART;VALUE=DATE:${dt.startStr}`);
    lines.push(`DTEND;VALUE=DATE:${dt.endStr}`);
  } else {
    lines.push(`DTSTART:${dt.startStr}`);
    lines.push(`DTEND:${dt.endStr}`);
  }
  if (ev.location) lines.push(`LOCATION:${escIcs(ev.location)}`);
  if (ev.description) lines.push(`DESCRIPTION:${escIcs(ev.description)}`);
  if (ev.link) lines.push(`URL:${ev.link}`);
  lines.push("END:VEVENT", "END:VCALENDAR");
  const ics = lines.join("\r\n");
  return `data:text/calendar;charset=utf-8,${encodeURIComponent(ics)}`;
}

function escIcs(s: string): string {
  return s.replace(/\\/g, "\\\\").replace(/;/g, "\\;").replace(/,/g, "\\,").replace(/\n/g, "\\n");
}
