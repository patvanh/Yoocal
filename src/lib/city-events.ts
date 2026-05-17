import fs from "node:fs/promises";
import path from "node:path";



// Heber Center: 40.5071, -111.4133 (Heber City, UT)
// Reject events outside ~15 miles OR with Park City addresses
function filterContaminatedHeber(events: any[]): any[] {
  const HEBER_LAT = 40.5071;
  const HEBER_LNG = -111.4133;
  const RADIUS_MILES = 15;
  const BAD_LOCATION_KEYWORDS = [
    "draper",
    "salt lake city",
    "orem",
    "lehi",
    "oakley",
    "pleasant grove",
    "american fork",
    "sandy, ut",
    "provo",
    "park city",
    "egyptian theatre",
    "deer valley",
    "kimball",
    "snow park",
    "high west distillery",
    "no name saloon",
    "spur bar",
    "park city mountain",
    "kearns blvd",
    "main st, park city",
  ];

  function milesBetween(lat1: number, lng1: number, lat2: number, lng2: number): number {
    const toRad = (d: number) => (d * Math.PI) / 180;
    const R = 3958.8;
    const dLat = toRad(lat2 - lat1);
    const dLng = toRad(lng2 - lng1);
    const a =
      Math.sin(dLat / 2) ** 2 +
      Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(a));
  }

  return events.filter((e: any) => {
    const loc = String(e.location ?? "").toLowerCase();
    if (BAD_LOCATION_KEYWORDS.some((kw) => loc.includes(kw))) return false;
    const lat = typeof e.lat === "string" ? parseFloat(e.lat) : e.lat;
    const lng = typeof e.lng === "string" ? parseFloat(e.lng) : e.lng;
    if (Number.isFinite(lat) && Number.isFinite(lng)) {
      const dist = milesBetween(HEBER_LAT, HEBER_LNG, lat, lng);
      if (dist > RADIUS_MILES) return false;
    }
    return true;
  });
}
/**
 * Event shape based on actual JSON in public/.
 * Some fields are optional because the scrapers don't always fill them.
 */
export type YoocalEvent = {
  title: string;
  date: string;            // "YYYY-MM-DD"
  description?: string;
  location?: string;
  link?: string;           // event detail URL on source site
  source?: string;         // "The Park Record", "Siebkens Resort", etc.
  source_url?: string;
  start_time?: string;     // "10:00 AM"
  end_time?: string;
  is_free?: boolean | null;
  price?: string;
  lat?: number;
  lng?: number;
  // tolerate unknown extra fields
  [key: string]: unknown;
};

export type CityKey = "parkcity" | "elkhartlake" | "heber" | "jackson";

export const CITY_CONFIG: Record<
  CityKey,
  { label: string; emoji: string; jsonFile: string }
> = {
  parkcity: {
    label: "Park City",
    emoji: "⛷️",
    jsonFile: "events.json",
  },
  elkhartlake: {
    label: "Elkhart Lake",
    emoji: "🏁",
    jsonFile: "events-elkhartlake.json",
  },
  heber: {
    label: "Heber Valley",
    emoji: "🚂",
    jsonFile: "events-heber.json",
  },
  jackson: {
    label: "Jackson Hole",
    emoji: "🏔️",
    jsonFile: "events-jackson.json",
  },
};

/**
 * Load events for a city. Accepts both wrapped { events: [...] } and bare [...] JSON.
 */
export async function loadCityEvents(city: CityKey): Promise<YoocalEvent[]> {
  const filePath = path.join(process.cwd(), "public", CITY_CONFIG[city].jsonFile);
  try {
    const raw = await fs.readFile(filePath, "utf-8");
    const parsed = JSON.parse(raw);
    let events: YoocalEvent[] = [];
    if (Array.isArray(parsed)) events = parsed as YoocalEvent[];
    else if (Array.isArray(parsed?.events)) events = parsed.events as YoocalEvent[];
    if (city === "heber") events = filterContaminatedHeber(events);
    return events;
    // legacy fallthrough (will not run):
    if (false) {}
    return [];
  } catch (err) {
    console.error(`[loadCityEvents] failed for ${city}:`, err);
    return [];
  }
}

/**
 * Compute the "weekend" window — Friday 00:00 through Sunday 23:59 — that's
 * closest to today.
 *
 * Rules:
 *   - If today is Fri/Sat/Sun, this weekend IS today's weekend.
 *   - Otherwise (Mon–Thu), fast-forward to the upcoming Friday.
 *   - "now" is computed in America/Denver (Park City) — close enough for
 *     Elkhart Lake too, since the date boundary only matters at midnight.
 */
export function computeWeekendWindow(reference: Date = new Date()): {
  start: Date;        // Friday 00:00
  end: Date;          // Monday 00:00 (exclusive)
  days: { date: Date; iso: string; label: string }[];
} {
  // Work in local-ish terms using the reference's UTC parts, then shift back.
  // We just need date boundaries, not precise minute math.
  const ref = new Date(reference);
  ref.setHours(0, 0, 0, 0);

  const day = ref.getDay(); // 0=Sun ... 5=Fri ... 6=Sat
  const friday = new Date(ref);

  if (day === 5) {
    // Friday today
  } else if (day === 6) {
    // Saturday → friday was yesterday
    friday.setDate(friday.getDate() - 1);
  } else if (day === 0) {
    // Sunday → friday was 2 days ago
    friday.setDate(friday.getDate() - 2);
  } else {
    // Mon(1)–Thu(4) → days until Friday = 5 - day
    friday.setDate(friday.getDate() + (5 - day));
  }

  const monday = new Date(friday);
  monday.setDate(monday.getDate() + 3);

  const days = [0, 1, 2].map((offset) => {
    const d = new Date(friday);
    d.setDate(friday.getDate() + offset);
    const iso = formatLocalISODate(d);
    const label = d.toLocaleDateString("en-US", {
      weekday: "long",
      month: "long",
      day: "numeric",
    });
    return { date: d, iso, label };
  });

  return { start: friday, end: monday, days };
}

/** Local-date ISO string (YYYY-MM-DD) without UTC shift weirdness. */
export function formatLocalISODate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/**
 * Filter events occurring within the weekend window, grouped by day.
 * Returns three buckets — Friday, Saturday, Sunday — each sorted by start_time.
 */
export function groupEventsByDay(
  events: YoocalEvent[],
  window: ReturnType<typeof computeWeekendWindow>,
): { day: { iso: string; label: string }; events: YoocalEvent[] }[] {
  const buckets = window.days.map((d) => ({
    day: { iso: d.iso, label: d.label },
    events: [] as YoocalEvent[],
  }));

  for (const ev of events) {
    if (!ev.date) continue;
    const eventIso = ev.date.slice(0, 10);
    const bucket = buckets.find((b) => b.day.iso === eventIso);
    if (bucket) bucket.events.push(ev);
  }

  for (const bucket of buckets) {
    bucket.events.sort((a, b) => sortByStartTime(a, b));
  }

  return buckets;
}

function sortByStartTime(a: YoocalEvent, b: YoocalEvent): number {
  const at = parseTimeToMinutes(a.start_time);
  const bt = parseTimeToMinutes(b.start_time);
  // events without times go to the end of the day
  if (at === null && bt === null) return a.title.localeCompare(b.title);
  if (at === null) return 1;
  if (bt === null) return -1;
  return at - bt;
}

function parseTimeToMinutes(t?: string): number | null {
  if (!t) return null;
  const m = t.trim().match(/^(\d{1,2}):(\d{2})\s*(AM|PM)?$/i);
  if (!m) return null;
  let hour = parseInt(m[1], 10);
  const min = parseInt(m[2], 10);
  const ampm = m[3]?.toUpperCase();
  if (ampm === "PM" && hour !== 12) hour += 12;
  if (ampm === "AM" && hour === 12) hour = 0;
  return hour * 60 + min;
}

/**
 * Render-friendly free/price label.
 */
export function priceLabel(ev: YoocalEvent): string | null {
  if (ev.is_free === true) return "Free";
  if (ev.price && ev.price.trim()) return ev.price;
  return null;
}
