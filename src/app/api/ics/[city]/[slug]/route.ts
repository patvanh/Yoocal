import { NextRequest, NextResponse } from 'next/server';
import { cityKeyFromSlug, findEvent } from '@/lib/events';

// Convert a 12-hour time like "7:30 PM" to "HH:MM" 24-hour. Mirrors the detail page.
function to24h(time12: string | undefined | null): string {
  if (!time12) return '';
  const m = time12.trim().match(/^(\d{1,2}):?(\d{2})?\s*([AaPp][Mm])?$/);
  if (!m) return '';
  let h = parseInt(m[1], 10);
  const min = m[2] ? m[2] : '00';
  const ap = (m[3] || '').toLowerCase();
  if (ap === 'pm' && h < 12) h += 12;
  if (ap === 'am' && h === 12) h = 0;
  return `${String(h).padStart(2, '0')}:${min}`;
}

function addOneHourTo24h(time12: string | undefined | null): string {
  const t = to24h(time12);
  if (!t) return '';
  const [h, m] = t.split(':').map((x) => parseInt(x, 10));
  const nh = (h + 1) % 24;
  return `${String(nh).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
}

// .ics escaping: commas, semicolons, backslashes, newlines.
function esc(s: string): string {
  return (s || '')
    .replace(/\\/g, '\\\\')
    .replace(/;/g, '\\;')
    .replace(/,/g, '\\,')
    .replace(/\r?\n/g, '\\n');
}

// "2026-06-15" + "19:30" -> "20260615T193000" (floating local time, no TZ).
// Date-only (all-day) -> "20260615".
function icsStamp(date: string, time24?: string): string {
  const d = (date || '').slice(0, 10).replace(/-/g, '');
  if (!time24) return d;
  return `${d}T${time24.replace(':', '')}00`;
}

export async function GET(
  _req: NextRequest,
  ctx: { params: Promise<{ city: string; slug: string }> }
) {
  const { city, slug } = await ctx.params;
  const cityKey = cityKeyFromSlug(city);
  if (!cityKey) return NextResponse.json({ error: 'unknown city' }, { status: 404 });

  const event = findEvent(cityKey, slug);
  if (!event) return NextResponse.json({ error: 'event not found' }, { status: 404 });

  const startT = event.start_time ? to24h(event.start_time) : '';
  let endDate = event.end_date || event.date;
  let endT = '';
  if (event.end_time) endT = to24h(event.end_time);
  else if (event.start_time) { endT = addOneHourTo24h(event.start_time); endDate = event.date; }
  else endDate = event.end_date || event.date;

  const dtStart = icsStamp(event.date, startT || undefined);
  const dtEnd = icsStamp(endDate, endT || undefined);
  // All-day events use VALUE=DATE and the end date should be exclusive (+1 day),
  // but for a single all-day event most clients accept DTSTART only; keep it simple
  // and correct for the common timed case.
  const allDay = !startT;
  const uid = `${slug}-${event.date}@yoocal.com`;
  const stamp = new Date().toISOString().replace(/[-:]/g, '').replace(/\.\d+/, '');

  const lines = [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//Yoocal//Events//EN',
    'CALSCALE:GREGORIAN',
    'METHOD:PUBLISH',
    'BEGIN:VEVENT',
    `UID:${uid}`,
    `DTSTAMP:${stamp}`,
    allDay ? `DTSTART;VALUE=DATE:${dtStart}` : `DTSTART:${dtStart}`,
    allDay ? `DTEND;VALUE=DATE:${dtEnd}` : `DTEND:${dtEnd}`,
    `SUMMARY:${esc(event.title)}`,
    event.description ? `DESCRIPTION:${esc(event.description.slice(0, 800))}` : '',
    event.location ? `LOCATION:${esc(event.location)}` : '',
    event.link ? `URL:${esc(event.link)}` : '',
    'END:VEVENT',
    'END:VCALENDAR',
  ].filter(Boolean);

  const body = lines.join('\r\n');
  const filename = `${slug}.ics`;
  return new NextResponse(body, {
    status: 200,
    headers: {
      'Content-Type': 'text/calendar; charset=utf-8',
      'Content-Disposition': `attachment; filename="${filename}"`,
      'Cache-Control': 'public, max-age=3600',
    },
  });
}
