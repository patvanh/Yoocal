import { readFileSync } from 'fs'
import path from 'path'

export interface YoocalEvent {
  title: string
  date: string
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

export type CityKey = 'parkcity' | 'elkhartlake'

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
    aboutPage: 'about-park-city.html',
  },
  elkhartlake: {
    name: 'Elkhart Lake, WI',
    label: 'Elkhart Lake & Sheboygan County',
    slug: 'elkhart-lake',
    file: 'events-elkhartlake.json',
    center: [43.8358, -88.0051],
    zoom: 13,
    junk: ['previous month', 'next month'],
    aboutPage: 'about-elkhart-lake.html',
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

  return Array.from(dedupMap.values())
}

export function getAllEventsWithCity(): Array<YoocalEvent & { cityKey: CityKey; citySlug: string }> {
  const result: Array<YoocalEvent & { cityKey: CityKey; citySlug: string }> = []
  for (const [cityKey, config] of Object.entries(CITY_CONFIG) as [CityKey, typeof CITY_CONFIG[CityKey]][]) {
    const events = getEventsForCity(cityKey)
    events.forEach(e => result.push({ ...e, cityKey, citySlug: config.slug }))
  }
  return result
}

export function findEvent(cityKey: CityKey, slug: string): YoocalEvent | null {
  const events = getEventsForCity(cityKey)
  return events.find(e => eventSlug(e) === slug) || null
}

export function formatDate(dateStr: string): string {
  if (!dateStr) return ''
  const d = new Date(dateStr + 'T12:00:00')
  const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
  const months = ['January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December']
  return `${days[d.getDay()]}, ${months[d.getMonth()]} ${d.getDate()}, ${d.getFullYear()}`
}
