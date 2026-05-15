#!/usr/bin/env node
/* eslint-disable */
/**
 * Adds Heber Valley as a third city to the yoocal codebase.
 *
 * Edits 5 files:
 *   1. src/lib/events.ts                 — adds Heber to CITY_CONFIG, fixes lat/lng string parsing
 *   2. src/lib/city-events.ts            — adds heber to CityKey + CITY_CONFIG
 *   3. src/components/SiteNav.tsx        — accepts heber as cityKey
 *   4. src/components/CitySwitcher.tsx   — adds Heber pill tab
 *   5. src/lib/venues.ts                 — adds Heber venues + adds heber to VENUES_BY_CITY
 *
 * Idempotent: running it twice does NOT double-apply changes.
 *
 * Run from project root:
 *     node patches/add-heber.js
 */

const fs = require("fs");
const path = require("path");

const ROOT = process.cwd();
let edits = 0;

function readFile(rel) {
  return fs.readFileSync(path.join(ROOT, rel), "utf8");
}
function writeFile(rel, contents) {
  fs.writeFileSync(path.join(ROOT, rel), contents);
  edits++;
  console.log(`  ✓ ${rel}`);
}

console.log("Patching files to add Heber as a third city...\n");

// ---------- 1. src/lib/events.ts ----------
{
  const rel = "src/lib/events.ts";
  let s = readFile(rel);

  // Add 'heber' to CityKey union
  if (!s.includes("'heber'") && !s.includes('"heber"')) {
    s = s.replace(
      /export type CityKey = 'parkcity' \| 'elkhartlake'/,
      "export type CityKey = 'parkcity' | 'elkhartlake' | 'heber'",
    );
  }

  // Add Heber CITY_CONFIG block (after elkhartlake)
  if (!s.match(/heber: \{[\s\S]*?file: 'events-heber\.json'/)) {
    s = s.replace(
      /(\s*elkhartlake: \{[\s\S]*?aboutPage: '\/about\/elkhart-lake',\s*\},)/,
      "$1\n  heber: {\n    name: 'Heber Valley, UT',\n    label: 'Heber Valley',\n    slug: 'heber',\n    file: 'events-heber.json',\n    center: [40.5071, -111.4133],\n    zoom: 12,\n    junk: ['previous month', 'next month'],\n    aboutPage: '/about/heber',\n  },",
    );
  }

  // Add 'heber' to cityKeyFromSlug mapping
  if (!s.includes("'heber': 'heber'") && !s.includes("'heber-valley': 'heber'")) {
    s = s.replace(
      /'elkhart-lake': 'elkhartlake',/,
      "'elkhart-lake': 'elkhartlake',\n    'heber': 'heber',",
    );
  }

  // FIX: lat/lng come as strings in events-heber.json. Coerce to number on read.
  // Done by wrapping getEventsForCity output. We add a normalizer function.
  if (!s.includes("function coerceLatLng")) {
    // Insert helper just before getEventsForCity
    s = s.replace(
      /(export function getEventsForCity)/,
      "function coerceLatLng(events: YoocalEvent[]): YoocalEvent[] {\n  return events.map(e => {\n    const lat = typeof e.lat === 'string' ? parseFloat(e.lat) : e.lat\n    const lng = typeof e.lng === 'string' ? parseFloat(e.lng) : e.lng\n    return { ...e, lat: Number.isFinite(lat) ? lat : undefined, lng: Number.isFinite(lng) ? lng : undefined }\n  })\n}\n\n$1",
    );

    // Wrap the return value of getEventsForCity
    s = s.replace(
      /(export function getEventsForCity[\s\S]*?return )([^\n]+?)(\n)/,
      "$1coerceLatLng($2)$3",
    );
  }

  writeFile(rel, s);
}

// ---------- 2. src/lib/city-events.ts ----------
{
  const rel = "src/lib/city-events.ts";
  let s = readFile(rel);

  // Add 'heber' to CityKey type
  if (!/CityKey = "parkcity" \| "elkhartlake" \| "heber"/.test(s)) {
    s = s.replace(
      /export type CityKey = "parkcity" \| "elkhartlake"/,
      'export type CityKey = "parkcity" | "elkhartlake" | "heber"',
    );
  }

  // Add Heber entry to CITY_CONFIG
  if (!s.includes('jsonFile: "events-heber.json"')) {
    s = s.replace(
      /(elkhartlake: \{[\s\S]*?jsonFile: "events-elkhartlake\.json",\s*\},)/,
      '$1\n  heber: {\n    label: "Heber Valley",\n    emoji: "🚂",\n    jsonFile: "events-heber.json",\n  },',
    );
  }

  writeFile(rel, s);
}

// ---------- 3. src/components/SiteNav.tsx ----------
{
  const rel = "src/components/SiteNav.tsx";
  let s = readFile(rel);

  // Add heber to CityKey type
  if (!/CityKey = "parkcity" \| "elkhartlake" \| "heber"/.test(s)) {
    s = s.replace(
      /type CityKey = "parkcity" \| "elkhartlake";/,
      'type CityKey = "parkcity" | "elkhartlake" | "heber";',
    );
  }

  // Add heber to aboutHref ternary chain
  if (!s.includes('"/about/heber"')) {
    s = s.replace(
      /const aboutHref =\s*cityKey === "parkcity"\s*\?\s*"\/about\/park-city"\s*:\s*cityKey === "elkhartlake"\s*\?\s*"\/about\/elkhart-lake"\s*:\s*"\/about";/,
      'const aboutHref =\n    cityKey === "parkcity"\n      ? "/about/park-city"\n      : cityKey === "elkhartlake"\n        ? "/about/elkhart-lake"\n        : cityKey === "heber"\n          ? "/about/heber"\n          : "/about";',
    );
  }

  // Add heber to aboutLabel ternary chain
  if (!s.includes('"About Heber"')) {
    s = s.replace(
      /const aboutLabel =\s*cityKey === "parkcity"\s*\?\s*"About Park City"\s*:\s*cityKey === "elkhartlake"\s*\?\s*"About Elkhart Lake"\s*:\s*"About";/,
      'const aboutLabel =\n    cityKey === "parkcity"\n      ? "About Park City"\n      : cityKey === "elkhartlake"\n        ? "About Elkhart Lake"\n        : cityKey === "heber"\n          ? "About Heber"\n          : "About";',
    );
  }

  writeFile(rel, s);
}

// ---------- 4. src/components/CitySwitcher.tsx ----------
{
  const rel = "src/components/CitySwitcher.tsx";
  let s = readFile(rel);

  // Widen the `active` and switchTo type unions
  s = s.replace(
    /active: "parkcity" \| "elkhartlake";/,
    'active: "parkcity" | "elkhartlake" | "heber";',
  );
  s = s.replace(
    /function switchTo\(city: "parkcity" \| "elkhartlake"\)/,
    'function switchTo(city: "parkcity" | "elkhartlake" | "heber")',
  );
  s = s.replace(
    /\{ key: "parkcity" \| "elkhartlake"; label: string; emoji: string \}/,
    '{ key: "parkcity" | "elkhartlake" | "heber"; label: string; emoji: string }',
  );

  // Add Heber to tabs array (after elkhartlake)
  if (!s.includes('key: "heber"')) {
    s = s.replace(
      /(\{\s*key:\s*"elkhartlake",\s*label:\s*"Elkhart Lake",\s*emoji:\s*"🏁"\s*\},)/,
      '$1\n    { key: "heber", label: "Heber Valley", emoji: "🚂" },',
    );
  }

  writeFile(rel, s);
}

// ---------- 5. src/lib/venues.ts ----------
{
  const rel = "src/lib/venues.ts";
  let s = readFile(rel);

  // Widen VENUES_BY_CITY type
  s = s.replace(
    /export const VENUES_BY_CITY: Record<"parkcity" \| "elkhartlake", Venue\[\]> = \{/,
    'export const VENUES_BY_CITY: Record<"parkcity" | "elkhartlake" | "heber", Venue[]> = {',
  );

  // Add Heber venues block before the closing brace
  if (!s.includes("Heber Valley Railroad")) {
    s = s.replace(
      /(\s*\],\s*\};)(\s*\n\/\*\* Human-readable label for a tag\.)/,
      `$1
  heber: [
    {
      name: "Heber Valley Railroad",
      emoji: "🚂",
      address: "450 S 600 W, Heber City, UT 84032",
      tags: ["family", "community"],
      desc: "Historic train excursions through Heber Valley on a real steam railroad. Dinner trains, holiday rides, North Pole Express, and seasonal special events all year long.",
      matchAliases: ["Heber Valley Railroad", "Heber Railroad"],
    },
    {
      name: "Soldier Hollow",
      emoji: "🎿",
      address: "1370 W Soldier Hollow Ln, Midway, UT 84049",
      tags: ["sports", "outdoor", "family"],
      desc: "2002 Olympic biathlon and cross-country venue. Tubing in winter, hiking and biking in summer, plus the famous Soldier Hollow Classic sheepdog championships every Labor Day weekend.",
      matchAliases: ["Soldier Hollow Nordic Center"],
    },
    {
      name: "Deer Creek Reservoir",
      emoji: "🚣",
      address: "Deer Creek State Park, UT-189, Heber City, UT 84032",
      tags: ["outdoor", "sports", "family"],
      desc: "Beautiful state-park reservoir between Heber and Provo Canyon. Boating, paddleboarding, swimming, kayaking, and fishing with Wasatch views — calmer than Jordanelle.",
      matchAliases: ["Deer Creek State Park", "Deer Creek"],
    },
    {
      name: "Homestead Crater",
      emoji: "🌋",
      address: "700 Homestead Dr, Midway, UT 84049",
      tags: ["wellness", "family", "outdoor"],
      desc: "A geothermal hot spring inside a 55-foot limestone dome. Swimming, snorkeling, and SCUBA in 90°F mineral water year-round — one of the most unique experiences in Utah.",
      matchAliases: ["Homestead Resort"],
    },
    {
      name: "Heber Valley Cheese & Dairy",
      emoji: "🐄",
      address: "920 N 1300 W, Heber City, UT 84032",
      tags: ["family", "food", "community"],
      desc: "Working family dairy offering daily farm tours, fresh ice cream, cheese tastings, and barn visits. A hands-on look at Heber Valley's farming heritage that kids especially love.",
      matchAliases: ["Heber Valley Artisan Cheese", "Heber Valley Cheese", "Dairy Farm Tour"],
    },
    {
      name: "Midway Town Hall",
      emoji: "🏛️",
      address: "75 N 100 W, Midway, UT 84049",
      tags: ["community", "arts", "family"],
      desc: "Heart of historic Midway, hosting community events, town meetings, Swiss Days celebrations every Labor Day weekend, and seasonal programs throughout the year.",
      matchAliases: ["Midway"],
    },
  ],$2`,
    );
  }

  writeFile(rel, s);
}

console.log(`\n✓ Done — ${edits} files updated.`);
console.log("\nNext steps:");
console.log("  1. Confirm the About Heber page is at src/app/about/heber/page.tsx");
console.log("  2. Run: pkill -f 'next' && sleep 2 && npx next dev --webpack");
console.log("  3. Test these URLs in your browser:");
console.log("     - http://localhost:3000/about/heber");
console.log("     - http://localhost:3000/this-weekend?city=heber");
console.log("     - http://localhost:3000/venues?city=heber");
console.log("     - http://localhost:3000/park-city/los-lobos-2026-05-14  (regression)");
