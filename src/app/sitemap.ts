import type { MetadataRoute } from 'next';
import fs from 'fs';
import path from 'path';
import { slugify, CITY_CONFIG } from '@/lib/events';
import { CITY_ORDER } from '@/lib/cities';

const BASE = 'https://www.yoocal.com';

// City slug + event file, derived from the shared CITY_CONFIG in display order.
const CITY_FILES: Array<{ slug: string; file: string }> =
  CITY_ORDER.map((k) => ({ slug: CITY_CONFIG[k].slug, file: CITY_CONFIG[k].file }));

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
  // Real content-modification time for sitemap lastmod (data rebuilds nightly).
  const buildDate = new Date();

  // Per-city URLs, generated from the shared city list so a new city is never
  // silently missing from the sitemap (an SEO hole). Hub + about + intent hubs.
  const INTENT_HUBS: Array<{ seg: string; priority: number }> = [
    { seg: 'this-weekend', priority: 0.8 },
    { seg: 'free-events', priority: 0.7 },
    { seg: 'concerts', priority: 0.7 },
    { seg: 'this-month', priority: 0.7 },
  ];
  const citySlugs = CITY_ORDER.map((k) => CITY_CONFIG[k].slug);
  const cityPages: MetadataRoute.Sitemap = [
    ...citySlugs.map((slug) => ({
      url: `${BASE}/${slug}`, changeFrequency: 'daily' as const, priority: 0.95,
    })),
    ...citySlugs.map((slug) => ({
      url: `${BASE}/about/${slug}`, changeFrequency: 'weekly' as const, priority: 0.7,
    })),
    ...INTENT_HUBS.flatMap((h) =>
      citySlugs.map((slug) => ({
        url: `${BASE}/${slug}/${h.seg}`, changeFrequency: 'daily' as const, priority: h.priority,
      })),
    ),
  ];

  // Static (non-city) pages
  const staticPages: MetadataRoute.Sitemap = [
    { url: BASE, changeFrequency: 'daily', priority: 1.0 },
    { url: `${BASE}/about`, changeFrequency: 'weekly', priority: 0.6 },
    ...cityPages,
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

      // lastModified is when the PAGE/content last changed, not the (future)
      // event date. Event data regenerates nightly via the scraper cron, so
      // the build/generation time is the honest modification time. Using the
      // future event date here was semantically invalid (a lastmod can't be
      // in the future) and gave crawlers a misleading freshness signal.
      eventPages.push({
        url,
        lastModified: buildDate,
        changeFrequency: 'daily',
        priority: 0.7,
      });
    }
  }

  return [...staticPages, ...eventPages];
}
