// Shared city-search data and option-builder used by both the home page
// (HomeBrand) and the city calendar pages (CalendarClient), so the search
// dropdown behaves identically everywhere.

export type City = {
  key: string
  name: string
  region: string
  emoji: string
  blurb: string
  founder?: boolean
}

export const CITIES: City[] = [
  { key: "parkcity", name: "Park City", region: "Utah", emoji: "",
    blurb: "Concerts, festivals, races, outdoor adventures and more.", founder: true },
  { key: "jackson", name: "Jackson Hole", region: "Wyoming", emoji: "",
    blurb: "Music festivals, chamber events, and Teton County happenings." },
  { key: "heber", name: "Heber Valley", region: "Utah", emoji: "",
    blurb: "Rodeos, fairs, train rides and small-town events across the Wasatch Back." },
  { key: "elkhartlake", name: "Elkhart Lake", region: "Wisconsin", emoji: "",
    blurb: "Racing, lakeside events and everything around Road America." },
  { key: "greenlake", name: "Green Lake", region: "Wisconsin", emoji: "",
    blurb: "Golf, boating, summer concerts and small-town events on Wisconsin’s deepest lake." },
]

// ZIP -> city key. Small static map for the 4 live cities; expand as we grow.
export const ZIP_TO_CITY: Record<string, string> = {
  "84060": "parkcity", "84068": "parkcity", "84098": "parkcity",
  "83001": "jackson", "83002": "jackson", "83014": "jackson", "83025": "jackson",
  "84032": "heber", "84049": "heber",
  "53020": "elkhartlake",
  "54941": "greenlake", "54971": "greenlake", "54968": "greenlake",
}

// Aliases — typing these resolves to the matching city
export const ALIASES: Record<string, string> = {
  "pc": "parkcity", "park city ut": "parkcity",
  "jh": "jackson", "jackson wy": "jackson",
  "midway": "heber", "wasatch back": "heber",
  "road america": "elkhartlake",
  "green lake wi": "greenlake", "lawsonia": "greenlake", "princeton wi": "greenlake",
}

export type SearchOption =
  | { kind: "city"; city: City }
  | { kind: "request"; rawQuery: string }

function normalizeQuery(raw: string): string {
  return raw.toLowerCase().trim().replace(/,\s*[a-z .]+$/, "").replace(/\s+/g, " ")
}

export function buildCityOptions(raw: string): SearchOption[] {
  const trimmed = raw.trim()
  if (!trimmed) return []

  // Pure-digit input: match ZIPs by prefix so "840" surfaces all 840xx cities.
  if (/^\d+$/.test(trimmed)) {
    if (trimmed.length === 5) {
      const k = ZIP_TO_CITY[trimmed]
      if (k) {
        const c = CITIES.find((x) => x.key === k)
        if (c) return [{ kind: "city", city: c }]
      }
      return [{ kind: "request", rawQuery: trimmed }]
    }
    // Partial ZIP — collect distinct cities whose ZIPs start with these digits.
    const keys = new Set<string>()
    for (const [zip, key] of Object.entries(ZIP_TO_CITY)) {
      if (zip.startsWith(trimmed)) keys.add(key)
    }
    const opts: SearchOption[] = [...keys]
      .map((k) => CITIES.find((c) => c.key === k))
      .filter((c): c is City => !!c)
      .map((c) => ({ kind: "city", city: c }))
    if (opts.length) return opts
    return [{ kind: "request", rawQuery: trimmed }]
  }

  const q = normalizeQuery(trimmed)

  // Alias direct hit
  if (ALIASES[q]) {
    const c = CITIES.find((x) => x.key === ALIASES[q])
    if (c) return [{ kind: "city", city: c }]
  }

  // Substring match against name + region + key
  const matches = CITIES.filter((c) => {
    const hay = `${c.name} ${c.region} ${c.key}`.toLowerCase()
    return hay.includes(q)
  })
  const opts: SearchOption[] = matches.map((c) => ({ kind: "city", city: c }))
  opts.push({ kind: "request", rawQuery: trimmed })
  return opts
}
