import { readFileSync } from 'fs'
import path from 'path'

export interface YoocalEvent {
  title: string
  date: string
  end_date?: string
  description?: string
  location?: string
  link?: string
  source?: string
  source_url?: string
  price?: string
  is_free?: boolean | null
  scraped_at?: string
  start_time?: string
  end_time?: string
  recurrence?: string
  recurrence_day?: string
  recurrence_days?: string
  lat?: number
  lng?: number
  featured?: boolean
}

export interface EventsFile {
  updated_at?: string
  scraped_at?: string
  total: number
  events: YoocalEvent[]
}

export type CityKey = 'parkcity' | 'elkhartlake' | 'heber' | 'jackson'

// Precise coordinates for known venues
export const VENUE_COORDS: Record<string, [number, number]> = {
  // Park City main venues — verified via Google Geocoding API
  'egyptian theatre': [40.6426, -111.4949],
  'kimball arts center': [40.6605, -111.5040],
  'park city library': [40.6507, -111.5031],
  'park city film': [40.6507, -111.5031],
  'high west distillery': [40.6441, -111.4976],
  'high west': [40.6441, -111.4976],
  'no name saloon': [40.6438, -111.4962],
  'spur bar': [40.6438, -111.4962],
  'the spur': [40.6438, -111.4962],
  'old town': [40.6438, -111.4962],
  'main street': [40.6438, -111.4962],
  'deer valley': [40.6226, -111.4851],
  'snow park': [40.6226, -111.4851],
  'park city mountain': [40.6589, -111.5468],
  'pcmr': [40.6589, -111.5468],
  'swaner preserve': [40.7217, -111.5377],
  'swaner': [40.7217, -111.5377],
  'kimball junction': [40.7021, -111.5423],
  'jordanelle': [40.6000, -111.4280],
  'basin rec': [40.6516, -111.5080],
  'fieldhouse': [40.6516, -111.5080],
  'park city municipal': [40.6494, -111.5013],
  'summit community gardens': [40.6530, -111.5050],
  // Elkhart Lake venues — verified
  'road america': [43.7997, -88.0131],
  'siebkens resort': [43.8305, -88.0175],
  'siebkens': [43.8305, -88.0175],
  'osthoff': [43.8304, -88.0147],
  'the osthoff': [43.8304, -88.0147],
  'throttlestop': [43.8336, -88.0074],
  'elkhart lake': [43.8358, -88.0051],
  // Heber Valley venues — verified
  'heber valley railroad': [40.5023, -111.4245],
  'deer creek': [40.6000, -111.4280],
  'jordanelle reservoir': [40.6000, -111.4280],
  // Jackson Hole, WY venues
  'center for the arts': [43.4775, -110.7654],
  'walk festival hall': [43.5874, -110.8284],
  'snow king mountain': [43.4694, -110.7585],
  'jackson hole high school': [43.4901, -110.7651],
  'jackson hole mountain resort': [43.5875, -110.8281],
  'teton village': [43.5875, -110.8281],
  'teton village commons': [43.5879, -110.8278],
  'murie ranch': [43.6603, -110.7038],
  'teton county library': [43.4799, -110.7624],
  'jackson hole rodeo': [43.4794, -110.7659],
  'fairgrounds': [43.4731, -110.7689],
}

export function getVenueCoords(location: string): [number, number] | null {
  if (!location) return null
  const loc = location.toLowerCase()
  for (const [venue, coords] of Object.entries(VENUE_COORDS)) {
    if (loc.includes(venue)) return coords
  }
  return null
}

export const CITY_CONFIG: Record<CityKey, {
  name: string
  label: string
  slug: string
  file: string
  supplementalFile?: string
  center: [number, number]
  zoom: number
  junk: string[]
  aboutPage: string
}> = {
  parkcity: {
    name: 'Park City, UT',
    label: 'Park City & Summit County',
    slug: 'park-city',
    file: 'events.json',
    supplementalFile: 'events-heber.json',
    center: [40.6461, -111.4980],
    zoom: 12,
    junk: ['not just a ski town', 'summer hiking', 'treat yourself', 'shopping', 'previous month', 'next month'],
    aboutPage: '/about/park-city',
  },
  elkhartlake: {
    name: 'Elkhart Lake, WI',
    label: 'Elkhart Lake & Sheboygan County',
    slug: 'elkhart-lake',
    file: 'events-elkhartlake.json',
    center: [43.8358, -88.0051],
    zoom: 13,
    junk: ['previous month', 'next month'],
    aboutPage: '/about/elkhart-lake',
  },
  heber: {
    name: 'Heber Valley, UT',
    label: 'Heber Valley',
    slug: 'heber',
    file: 'events-heber.json',
    center: [40.5071, -111.4133],
    zoom: 12,
    junk: ['previous month', 'next month'],
    aboutPage: '/about/heber',
  },
  jackson: {
    name: 'Jackson Hole, WY',
    label: 'Jackson Hole & Teton County',
    slug: 'jackson-hole',
    file: 'events-jackson.json',
    center: [43.4799, -110.7624],
    zoom: 11,
    junk: ['previous month', 'next month'],
    aboutPage: '/about/jackson-hole',
  },
}

export function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^\w\s-]/g, '')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-+|-+$/g, '')
    .substring(0, 80)
}

export function eventSlug(event: YoocalEvent): string {
  return `${slugify(event.title)}-${event.date}`
}

export function cityKeyFromSlug(slug: string): CityKey | null {
  const map: Record<string, CityKey> = {
    'park-city': 'parkcity',
    'elkhart-lake': 'elkhartlake',
    'heber': 'heber',
    'jackson-hole': 'jackson',
  }
  return map[slug] || null
}

function loadFile(filename: string): YoocalEvent[] {
  try {
    const filePath = path.join(process.cwd(), 'public', filename)
    const data: EventsFile = JSON.parse(readFileSync(filePath, 'utf-8'))
    return data.events || []
  } catch {
    return []
  }
}

function coerceLatLng(events: YoocalEvent[]): YoocalEvent[] {
  return events.map(e => {
    const lat = typeof e.lat === 'string' ? parseFloat(e.lat) : e.lat
    const lng = typeof e.lng === 'string' ? parseFloat(e.lng) : e.lng
    return { ...e, lat: Number.isFinite(lat) ? lat : undefined, lng: Number.isFinite(lng) ? lng : undefined }
  })
}

export function getEventsForCity(cityKey: CityKey): YoocalEvent[] {
  const config = CITY_CONFIG[cityKey]
  let events = loadFile(config.file)

  if (config.supplementalFile) {
    const supp = loadFile(config.supplementalFile)
    events = [...events, ...supp]
  }

  // Filter junk
  events = events.filter(e =>
    !config.junk.some(j => (e.title || '').toLowerCase().includes(j))
  )

  // Deduplicate: same title+date, prefer Park Record or events with start_time
  const dedupMap = new Map<string, YoocalEvent>()
  events.forEach(e => {
    const titleClean = (e.title || '').toLowerCase().replace(/^[("'\-\s]+/, '').substring(0, 35)
    const key = `${titleClean}|${(e.date || '').substring(0, 10)}`
    const existing = dedupMap.get(key)
    if (!existing) {
      dedupMap.set(key, e)
    } else {
      const eScore = (e.source === 'The Park Record' ? 2 : 0) + (e.start_time ? 1 : 0)
      const exScore = (existing.source === 'The Park Record' ? 2 : 0) + (existing.start_time ? 1 : 0)
      if (eScore > exScore) dedupMap.set(key, e)
    }
  })

  return coerceLatLng(Array.from(dedupMap.values()))
}

export function getAllEventsWithCity(): Array<YoocalEvent & { cityKey: CityKey; citySlug: string }> {
  const result: Array<YoocalEvent & { cityKey: CityKey; citySlug: string }> = []
  for (const [cityKey, config] of Object.entries(CITY_CONFIG) as [CityKey, typeof CITY_CONFIG[CityKey]][]) {
    const events = getEventsForCity(cityKey)
    events.forEach(e => result.push({ ...e, cityKey, citySlug: config.slug }))
  }
  return result
}

// Loosen a slug for tolerant matching: collapse repeated dashes and remove
// dashes so old apostrophe-format slugs (e.g. "people-s-market") match the
// current format ("peoples-market"). This keeps previously-indexed URLs alive
// after slugify changes, avoiding 404s.
function looseSlug(s: string): string {
  return s.replace(/-+/g, '-').replace(/-/g, '')
}

export function findEvent(cityKey: CityKey, slug: string): YoocalEvent | null {
  const events = getEventsForCity(cityKey)
  // 1. Exact match (fast path, current format).
  const exact = events.find(e => eventSlug(e) === slug)
  if (exact) return exact
  // 2. Tolerant match — handles legacy slug formats (apostrophe handling, etc.)
  //    so old indexed URLs still resolve instead of 404ing.
  const loose = looseSlug(slug)
  return events.find(e => looseSlug(eventSlug(e)) === loose) || null
}

export function formatDate(dateStr: string): string {
  if (!dateStr) return ''
  const d = new Date(dateStr + 'T12:00:00')
  const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
  const months = ['January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December']
  return `${days[d.getDay()]}, ${months[d.getMonth()]} ${d.getDate()}, ${d.getFullYear()}`
}
