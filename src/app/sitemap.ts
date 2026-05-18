import type { MetadataRoute } from 'next';
import fs from 'fs';
import path from 'path';

const BASE = 'https://www.yoocal.com';

const CITY_FILES: Array<{ slug: string; file: string }> = [
  { slug: 'park-city', file: 'events.json' },
  { slug: 'elkhart-lake', file: 'events-elkhartlake.json' },
  { slug: 'heber', file: 'events-heber.json' },
  { slug: 'jackson-hole', file: 'events-jackson.json' },
];

function loadEvents(filename: string): any[] {
  try {
    const filePath = path.join(process.cwd(), 'public', filename);
    const raw = fs.readFileSync(filePath, 'utf-8');
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) return parsed;
    if (Array.isArray(parsed?.events)) return parsed.events;
    return [];
  } catch {
    return [];
  }
}

function slugify(s: string): string {
  return (s || '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 80);
}

export default function sitemap(): MetadataRoute.Sitemap {
  const today = new Date().toISOString().slice(0, 10);

  // Static pages
  const staticPages: MetadataRoute.Sitemap = [
    { url: BASE, changeFrequency: 'daily', priority: 1.0 },
    { url: `${BASE}/?city=parkcity`, changeFrequency: 'daily', priority: 0.9 },
    { url: `${BASE}/?city=elkhartlake`, changeFrequency: 'daily', priority: 0.9 },
    { url: `${BASE}/?city=heber`, changeFrequency: 'daily', priority: 0.9 },
    { url: `${BASE}/?city=jackson`, changeFrequency: 'daily', priority: 0.9 },
    { url: `${BASE}/about`, changeFrequency: 'weekly', priority: 0.6 },
    { url: `${BASE}/about/park-city`, changeFrequency: 'weekly', priority: 0.7 },
    { url: `${BASE}/about/elkhart-lake`, changeFrequency: 'weekly', priority: 0.7 },
    { url: `${BASE}/about/heber`, changeFrequency: 'weekly', priority: 0.7 },
    { url: `${BASE}/about/jackson-hole`, changeFrequency: 'weekly', priority: 0.7 },
    { url: `${BASE}/this-weekend`, changeFrequency: 'daily', priority: 0.8 },
    { url: `${BASE}/venues`, changeFrequency: 'weekly', priority: 0.6 },
    { url: `${BASE}/submit`, changeFrequency: 'monthly', priority: 0.5 },
  ];

  // Event pages — only future events, dedup by slug
  const eventPages: MetadataRoute.Sitemap = [];
  const seenSlugs = new Set<string>();

  for (const { slug: citySlug, file } of CITY_FILES) {
    const events = loadEvents(file);
    for (const e of events) {
      const date = (e.date || '').slice(0, 10);
      // Require ISO format YYYY-MM-DD; skip malformed or past dates
      if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) continue;
      if (date < today) continue;

      const titleSlug = slugify(e.title || '');
      if (!titleSlug) continue;

      const eventSlug = `${titleSlug}-${date}`;
      const url = `${BASE}/${citySlug}/${eventSlug}`;
      if (seenSlugs.has(url)) continue;
      seenSlugs.add(url);

      // Guard against malformed dates that would crash toISOString
      let lastMod: Date | undefined;
      const d = new Date(date);
      if (!isNaN(d.getTime())) lastMod = d;

      eventPages.push({
        url,
        changeFrequency: 'weekly',
        priority: 0.7,
        ...(lastMod ? { lastModified: lastMod } : {}),
      });
    }
  }

  return [...staticPages, ...eventPages];
}
