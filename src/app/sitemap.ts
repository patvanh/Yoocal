import type { MetadataRoute } from 'next';
import fs from 'fs';
import path from 'path';
import { slugify } from '@/lib/events';

const BASE = 'https://www.yoocal.com';

const CITY_FILES: Array<{ slug: string; file: string }> = [
  { slug: 'park-city', file: 'events.json' },
  { slug: 'elkhart-lake', file: 'events-elkhartlake.json' },
  { slug: 'heber', file: 'events-heber.json' },
  { slug: 'jackson-hole', file: 'events-jackson.json' },
  { slug: 'green-lake', file: 'events-greenlake.json' },
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

export default function sitemap(): MetadataRoute.Sitemap {
  const today = new Date().toISOString().slice(0, 10);

  // Static pages
  const staticPages: MetadataRoute.Sitemap = [
    { url: BASE, changeFrequency: 'daily', priority: 1.0 },
    { url: `${BASE}/park-city`, changeFrequency: 'daily', priority: 0.95 },
    { url: `${BASE}/elkhart-lake`, changeFrequency: 'daily', priority: 0.95 },
    { url: `${BASE}/heber`, changeFrequency: 'daily', priority: 0.95 },
    { url: `${BASE}/jackson-hole`, changeFrequency: 'daily', priority: 0.95 },
    { url: `${BASE}/green-lake`, changeFrequency: 'daily', priority: 0.95 },
    { url: `${BASE}/about`, changeFrequency: 'weekly', priority: 0.6 },
    { url: `${BASE}/about/park-city`, changeFrequency: 'weekly', priority: 0.7 },
    { url: `${BASE}/about/elkhart-lake`, changeFrequency: 'weekly', priority: 0.7 },
    { url: `${BASE}/about/heber`, changeFrequency: 'weekly', priority: 0.7 },
    { url: `${BASE}/about/jackson-hole`, changeFrequency: 'weekly', priority: 0.7 },
    { url: `${BASE}/about/green-lake`, changeFrequency: 'weekly', priority: 0.7 },
    { url: `${BASE}/park-city/this-weekend`, changeFrequency: 'daily', priority: 0.8 },
    { url: `${BASE}/jackson-hole/this-weekend`, changeFrequency: 'daily', priority: 0.8 },
    { url: `${BASE}/heber/this-weekend`, changeFrequency: 'daily', priority: 0.8 },
    { url: `${BASE}/elkhart-lake/this-weekend`, changeFrequency: 'daily', priority: 0.8 },
    { url: `${BASE}/green-lake/this-weekend`, changeFrequency: 'daily', priority: 0.8 },
    { url: `${BASE}/park-city/free-events`, changeFrequency: 'daily', priority: 0.7 },
    { url: `${BASE}/jackson-hole/free-events`, changeFrequency: 'daily', priority: 0.7 },
    { url: `${BASE}/heber/free-events`, changeFrequency: 'daily', priority: 0.7 },
    { url: `${BASE}/elkhart-lake/free-events`, changeFrequency: 'daily', priority: 0.7 },
    { url: `${BASE}/green-lake/free-events`, changeFrequency: 'daily', priority: 0.7 },
    { url: `${BASE}/park-city/concerts`, changeFrequency: 'daily', priority: 0.7 },
    { url: `${BASE}/jackson-hole/concerts`, changeFrequency: 'daily', priority: 0.7 },
    { url: `${BASE}/heber/concerts`, changeFrequency: 'daily', priority: 0.7 },
    { url: `${BASE}/elkhart-lake/concerts`, changeFrequency: 'daily', priority: 0.7 },
    { url: `${BASE}/green-lake/concerts`, changeFrequency: 'daily', priority: 0.7 },
    { url: `${BASE}/park-city/this-month`, changeFrequency: 'daily', priority: 0.7 },
    { url: `${BASE}/jackson-hole/this-month`, changeFrequency: 'daily', priority: 0.7 },
    { url: `${BASE}/heber/this-month`, changeFrequency: 'daily', priority: 0.7 },
    { url: `${BASE}/elkhart-lake/this-month`, changeFrequency: 'daily', priority: 0.7 },
    { url: `${BASE}/green-lake/this-month`, changeFrequency: 'daily', priority: 0.7 },
    { url: `${BASE}/venues`, changeFrequency: 'weekly', priority: 0.6 },
    { url: `${BASE}/for-businesses`, changeFrequency: 'weekly', priority: 0.7 },
    { url: `${BASE}/submit`, changeFrequency: 'monthly', priority: 0.5 },
  ];

  // Event pages — only future events within a 90-day window, dedup by slug.
  // 90 days balances SEO coverage (search engines crawl upcoming events)
  // with build speed. Events past the horizon are still accessible at their
  // canonical URLs, just not listed in the sitemap.
  const horizon = new Date();
  horizon.setDate(horizon.getDate() + 90);
  const horizonStr = horizon.toISOString().slice(0, 10);

  const eventPages: MetadataRoute.Sitemap = [];
  const seenSlugs = new Set<string>();

  for (const { slug: citySlug, file } of CITY_FILES) {
    const events = loadEvents(file);
    for (const e of events) {
      const date = (e.date || '').slice(0, 10);
      // Require ISO format YYYY-MM-DD; skip malformed, past, or far-future
      if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) continue;
      if (date < today) continue;
      if (date > horizonStr) continue;

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
