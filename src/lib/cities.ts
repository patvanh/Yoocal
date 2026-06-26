// Client-safe city metadata — the single source of truth for city lists in
// the UI (footer, nav, home, pickers). NO server-only imports (no fs/path), so
// this is safe to import from client components. Server code in events.ts also
// builds on this so there is one source.

export type CityKey = "parkcity" | "elkhartlake" | "heber" | "jackson" | "greenlake"

export interface CityMeta {
  key: CityKey
  slug: string
  name: string        // "Park City, UT" — short label with state
  shortName: string   // "Park City"
  region: string      // "Utah"
  label: string       // "Park City & Summit County" — long descriptor
  image: string       // "/cities/parkcity.jpg"
  blurb: string
  aboutPage: string
  founder?: boolean
}

export const CITIES: Record<CityKey, CityMeta> = {
  parkcity: {
    key: "parkcity", slug: "park-city", name: "Park City, UT", shortName: "Park City",
    region: "Utah", label: "Park City & Summit County", image: "/cities/parkcity.jpg",
    blurb: "Concerts, festivals, races, outdoor adventures and more.",
    aboutPage: "/about/park-city", founder: true,
  },
  heber: {
    key: "heber", slug: "heber", name: "Heber Valley, UT", shortName: "Heber Valley",
    region: "Utah", label: "Heber Valley", image: "/cities/heber.jpg",
    blurb: "Rodeos, fairs, train rides and small-town events across the Wasatch Back.",
    aboutPage: "/about/heber",
  },
  jackson: {
    key: "jackson", slug: "jackson-hole", name: "Jackson Hole, WY", shortName: "Jackson Hole",
    region: "Wyoming", label: "Jackson Hole & Teton County", image: "/cities/jackson.jpg",
    blurb: "Music festivals, chamber events, and Teton County happenings.",
    aboutPage: "/about/jackson-hole",
  },
  elkhartlake: {
    key: "elkhartlake", slug: "elkhart-lake", name: "Elkhart Lake, WI", shortName: "Elkhart Lake",
    region: "Wisconsin", label: "Elkhart Lake & Sheboygan County", image: "/cities/elkhartlake.jpg",
    blurb: "Racing, lakeside events and everything around Road America.",
    aboutPage: "/about/elkhart-lake",
  },
  greenlake: {
    key: "greenlake", slug: "green-lake", name: "Green Lake, WI", shortName: "Green Lake",
    region: "Wisconsin", label: "Green Lake Area", image: "/cities/greenlake.jpg",
    blurb: "Golf, boating, summer concerts and small-town events on Wisconsin's deepest lake.",
    aboutPage: "/about/green-lake",
  },
}

// Canonical display order for city lists across the UI.
export const CITY_ORDER: CityKey[] = ["parkcity", "heber", "jackson", "elkhartlake", "greenlake"]

// Convenience: cities in display order as an array.
export const CITIES_ORDERED: CityMeta[] = CITY_ORDER.map((k) => CITIES[k])
