'use client'

import CitySearch from "@/components/CitySearch"
import { useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useSearchParams } from 'next/navigation'
import EventModal, { type EventModalData } from './EventModal'

// ===== V2 EVENTS WIDGET =====
// Modern chips + cards UI with React state. Replaces the imperative DOM
// manipulation that used to live in the legacy calendar-section.
// Reads from /events.json (Park City). City switching still routes via
// the legacy ?city= param.

interface V2YocEvent {
  title: string
  date: string
  end_date?: string
  start_time?: string
  end_time?: string
  description?: string
  venue_name?: string
  location?: string
  address?: string
  lat?: number
  lng?: number
  link?: string
  source?: string
  image_url?: string
  categories?: string[]
  filter_categories?: string[]
  facets?: string[]
  hook?: string
  is_free?: boolean | null
  price?: string
}

// Search match: case-insensitive substring across title, description, venue,
// location, address, source, AND every category-ish field (categories,
// filter_categories, facets). Including filter_categories matters because that's
// where the clean user-facing buckets live ("Running & Races", "Outdoors"...) —
// without it, typing "running" misses everything tagged via the bucket pipeline.
function matchesQuery(e: V2YocEvent, qLower: string): boolean {
  if (!qLower) return true
  const text = [
    e.title, e.description, e.venue_name, e.location, e.address, e.source,
    ...(e.categories || []), ...(e.filter_categories || []), ...(e.facets || [])
  ].filter(Boolean).join(' ').toLowerCase()
  return text.includes(qLower)
}

function isFreeEvent(e: V2YocEvent): boolean {
  if (e.is_free === true) return true
  if (e.is_free === false) return false
  const text = `${e.title || ''} ${e.description || ''} ${e.price || ''}`.toLowerCase()
  return /\bfree\b/.test(text) || /\$0\b/.test(text) || /\bno charge\b/.test(text) || /\bno cost\b/.test(text)
}

type ChipId = 'weekend' | 'today' | 'free' | 'pickdate' | 'tomorrow' | 'next7' | 'music' | 'outdoors' | 'food' | 'family' | 'arts' | 'sports' | 'kids' | 'wellness' | 'education' | 'festivals'

function chipPassesEvent(chip: ChipId, e: V2YocEvent, todayStr: string, pickedDate: string): boolean {
  if (chip === 'free') return isFreeEvent(e)
  const eStart = (e.date || '').slice(0, 10)
  const eEnd = ((e.end_date || e.date) || '').slice(0, 10)
  if (!eStart) return false
  const onDay = (day: string) => eStart <= day && day <= (eEnd || eStart)
  if (chip === 'today') return onDay(todayStr)
  if (chip === 'pickdate') return onDay(pickedDate)
  if (chip === 'weekend') {
    const [y, m, d] = todayStr.split('-').map(Number)
    const t = new Date(y, m - 1, d)
    const dow = t.getDay()
    const daysToSat = (6 - dow + 7) % 7
    const sat = new Date(t); sat.setDate(t.getDate() + daysToSat)
    const sun = new Date(sat); sun.setDate(sat.getDate() + 1)
    const fmt = (x: Date) => `${x.getFullYear()}-${String(x.getMonth()+1).padStart(2,'0')}-${String(x.getDate()).padStart(2,'0')}`
    return onDay(fmt(sat)) || onDay(fmt(sun))
  }
  if (chip === 'tomorrow') {
    const [y, m, d] = todayStr.split('-').map(Number)
    const t = new Date(y, m - 1, d); t.setDate(t.getDate() + 1)
    const fmt = (x: Date) => `${x.getFullYear()}-${String(x.getMonth()+1).padStart(2,'0')}-${String(x.getDate()).padStart(2,'0')}`
    return onDay(fmt(t))
  }
  if (chip === 'next7') {
    const [y, m, d] = todayStr.split('-').map(Number)
    const end = new Date(y, m - 1, d); end.setDate(end.getDate() + 7)
    const endStr = `${end.getFullYear()}-${String(end.getMonth()+1).padStart(2,'0')}-${String(end.getDate()).padStart(2,'0')}`
    // Event overlaps the [today, today+7] window.
    return eStart <= endStr && (eEnd || eStart) >= todayStr
  }
  // Vibe chips: match against filter_categories (clean buckets), categories
  // (classifier output), AND title/description text via matchesQuery as fallback.
  const VIBE_TERMS: Record<string, string[]> = {
    music: ['music', 'concert', 'band', 'live music', 'symphony', 'opera', 'jazz', 'bluegrass'],
    outdoors: ['outdoors', 'outdoor', 'hike', 'hiking', 'trail', 'bike', 'mountain bike', 'paddle', 'kayak', 'climb', 'fish'],
    food: ['food & drink', 'food', 'wine', 'beer', 'brew', 'culinary', 'farmers market', 'taste'],
    family: ['family & kids', 'family', 'kids', 'children', 'kid-friendly'],
    arts: ['arts & theater', 'art', 'gallery', 'theater', 'theatre', 'museum', 'exhibit'],
    sports: ['sports', 'race', 'tournament', 'championship', 'game', 'match', 'rodeo'],
    kids: ['family & kids', 'kids', 'children', 'kid', 'toddler', 'storytime'],
    wellness: ['wellness', 'yoga', 'meditation', 'mindfulness', 'fitness', 'pilates'],
    education: ['education & talks', 'education', 'class', 'workshop', 'lecture', 'talk', 'workshop'],
    festivals: ['festivals', 'festival'],
  }
  const terms = VIBE_TERMS[chip]
  if (terms) {
    const haystack = [
      e.title, e.description, e.venue_name, e.location, e.source,
      ...(e.categories || []), ...(e.filter_categories || []), ...(e.facets || [])
    ].filter(Boolean).join(' ').toLowerCase()
    return terms.some(t => haystack.includes(t))
  }
  return true
}

type V2DayFilter = 'all' | 'today' | 'tomorrow' | 'weekend' | '7days' | 'pickdate'
type V2TimeFilter = 'any' | 'morning' | 'afternoon' | 'evening' | 'latenight'

// City center coordinates — fallback origin for the radius filter when the
// user has not shared their GPS location.
const CITY_CENTERS: Record<string, { lat: number; lng: number }> = {
  parkcity: { lat: 40.6461, lng: -111.4980 },
  heber: { lat: 40.5069, lng: -111.4133 },
  jackson: { lat: 43.4799, lng: -110.7624 },
  elkhartlake: { lat: 43.8336, lng: -87.9717 },
}

// Haversine distance in miles between two lat/lng points.
function v2DistanceMiles(lat1: number, lng1: number, lat2: number, lng2: number): number {
  const toRad = (d: number) => (d * Math.PI) / 180
  const R = 3958.8 // Earth radius in miles
  const dLat = toRad(lat2 - lat1)
  const dLng = toRad(lng2 - lng1)
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) *
    Math.sin(dLng / 2) * Math.sin(dLng / 2)
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
}

const V2_ALL_CATEGORIES = [
  'Music', 'Food & Drink', 'Outdoor', 'Family', 'Arts', 'Theater', 'Film',
  'Sports', 'Kids', 'Wellness', 'Education', 'Festival', 'Government', 'Community',
]
const V2_PRIMARY_CATEGORIES = ['Music', 'Food & Drink', 'Outdoor', 'Family']

const V2_CATEGORY_COLORS: Record<string, { bg: string; fg: string }> = {
  Music:          { bg: '#EEEDFE', fg: '#534AB7' },
  'Food & Drink': { bg: '#FAEEDA', fg: '#B45309' },
  Arts:           { bg: '#FCE7F3', fg: '#9D174D' },
  Theater:        { bg: '#EDE9FE', fg: '#5B21B6' },
  Film:           { bg: '#E0E7FF', fg: '#3730A3' },
  Sports:         { bg: '#DBEAFE', fg: '#1E40AF' },
  Outdoor:        { bg: '#D1FAE5', fg: '#065F46' },
  Family:         { bg: '#FFEDD5', fg: '#9A3412' },
  Kids:           { bg: '#FEF3C7', fg: '#92400E' },
  Wellness:       { bg: '#CCFBF1', fg: '#115E59' },
  Education:      { bg: '#FEF9C3', fg: '#854D0E' },
  Festival:       { bg: '#FEE2E2', fg: '#991B1B' },
  Government:     { bg: '#F1F5F9', fg: '#334155' },
  Community:      { bg: '#F3E8FF', fg: '#6B21A8' },
}

const V2_FACET_COLORS: Record<string, { bg: string; fg: string }> = {
  Free:      { bg: '#D1FAE5', fg: '#10b981' },
  '21+':     { bg: '#F1F5F9', fg: '#334155' },
  Paid:      { bg: '#FEF3C7', fg: '#B45309' },
  'Drop-in': { bg: '#F1F5F9', fg: '#334155' },
}


function v2TodayMountainStr(): string {
  // DST-aware Mountain calendar date as YYYY-MM-DD. en-CA formats as ISO.
  // Replaces manual offset math, which (a) hardcoded -6 and broke in MST
  // (Nov-Mar), and (b) round-tripped through toISOString() and shifted the
  // date a day in the evening when UTC had already crossed midnight.
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'America/Denver',
    year: 'numeric', month: '2-digit', day: '2-digit',
  }).format(new Date())
}

function v2TodayMountain(): Date {
  // Local-midnight Date of the current Mountain calendar day, so .getDate()/
  // .setDate() arithmetic and v2DateToStr() all operate consistently in local
  // fields (no UTC round-trip).
  const [y, m, d] = v2TodayMountainStr().split('-').map(Number)
  return new Date(y, m - 1, d)
}

function v2DateToStr(d: Date): string {
  // Read LOCAL fields to match how v2TodayMountain() builds the Date. Using
  // toISOString() here would re-convert to UTC and reintroduce the off-by-one.
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function v2ParseEventDate(s: string | undefined): Date | null {
  if (!s) return null
  const m = s.match(/^(\d{4})-(\d{2})-(\d{2})/)
  if (!m) return null
  return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]))
}

function v2ParseTime12h(t: string | undefined): number | null {
  if (!t) return null
  const m = t.trim().match(/^(\d{1,2}):?(\d{2})?\s*(AM|PM)?$/i)
  if (!m) return null
  let h = Number(m[1])
  const mn = Number(m[2] || 0)
  const ampm = (m[3] || '').toUpperCase()
  if (ampm === 'PM' && h < 12) h += 12
  if (ampm === 'AM' && h === 12) h = 0
  return h * 60 + mn
}

function v2FormatTimeDisplay(t: string | undefined): { hour: string; period: string } {
  if (!t) return { hour: '--', period: '' }
  const m = t.trim().match(/^(\d{1,2}):?(\d{2})?\s*(AM|PM)?$/i)
  if (!m) return { hour: t, period: '' }
  const h = m[1]
  const mn = m[2] || '00'
  const ampm = (m[3] || '').toUpperCase()
  return { hour: `${h}:${mn}`, period: ampm }
}

function v2WeekendDates(): { start: Date; end: Date } {
  const t = v2TodayMountain()
  const dow = t.getDay()
  let daysToFri = (5 - dow + 7) % 7
  if (dow === 5) daysToFri = 0
  const start = new Date(t)
  start.setDate(t.getDate() + daysToFri)
  const end = new Date(start)
  end.setDate(start.getDate() + 2)
  return { start, end }
}

function V2Chip({ active, onClick, children, color, compact = false }: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
  color?: { bg: string; fg: string }
  compact?: boolean
}) {
  const activeStyle = color
    ? { background: color.bg, color: color.fg, border: '1px solid transparent', fontWeight: 600 }
    : { background: '#534AB7', color: '#fff', border: '1px solid transparent', fontWeight: 500 }
  const inactiveStyle = {
    background: 'rgba(255,255,255,0.06)',
    color: '#fff',
    border: '1px solid rgba(255,255,255,0.18)',
  }
  return (
    <button
      onClick={onClick}
      style={{
        padding: compact ? '5px 12px' : '7px 14px',
        fontSize: compact ? 12 : 13,
        borderRadius: 999,
        whiteSpace: 'nowrap',
        cursor: 'pointer',
        fontFamily: "'DM Sans', sans-serif",
        transition: 'all 0.15s ease',
        ...(active ? activeStyle : inactiveStyle),
      }}
    >
      {children}
    </button>
  )
}

function V2CategoryPill({ name, role = 'category' }: { name: string; role?: 'category' | 'facet' }) {
  const colors = role === 'category' ? V2_CATEGORY_COLORS[name] : V2_FACET_COLORS[name]
  const fallback = { bg: '#F1F5F9', fg: '#334155' }
  const { bg, fg } = colors || fallback
  return (
    <span style={{
      background: bg, color: fg,
      fontSize: 11, padding: '2px 9px', borderRadius: 999,
      fontWeight: 600,
    }}>{name}</span>
  )
}

function V2EventCard({ event, onClick, featured = false, viewedDay }: { event: V2YocEvent; onClick: () => void; featured?: boolean; viewedDay?: string }) {
  // Multi-day events: if we're viewing a specific day inside the event's span,
  // badge THAT day (not the event's start), so a May 26-30 event shown on the
  // May 29 view reads "May 29", not a confusing "May 26". In range views
  // (no viewedDay passed) we badge the event's own start date.
  const startStr = (event.date || '').slice(0, 10)
  const endStr = (event.end_date || startStr).slice(0, 10)
  const isMultiDay = !!endStr && endStr > startStr
  const badgeStr = (viewedDay && startStr <= viewedDay && viewedDay <= endStr) ? viewedDay : startStr
  const date = v2ParseEventDate(badgeStr)
  const endDate = isMultiDay ? v2ParseEventDate(endStr) : null
  const MON = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
  const dayOfWeek = date ? ['SUN','MON','TUE','WED','THU','FRI','SAT'][date.getDay()] : '?'
  const monthDay = date ? `${MON[date.getMonth()]} ${date.getDate()}` : ''
  const thru = endDate ? `thru ${MON[endDate.getMonth()]} ${endDate.getDate()}` : ''
  const time = v2FormatTimeDisplay(event.start_time)
  return (
    <button
      onClick={onClick}
      style={{
        width: '100%', textAlign: 'left',
        background: featured ? 'rgba(45, 40, 83, 0.85)' : 'rgba(255,255,255,0.06)',
        border: featured ? '1px solid rgba(175,169,236,0.2)' : '1px solid rgba(255,255,255,0.10)',
        backdropFilter: 'blur(8px)',
        borderRadius: 10, padding: '12px 14px',
        display: 'flex', gap: 14, alignItems: 'flex-start',
        marginBottom: 0, cursor: 'pointer',
        fontFamily: "'DM Sans', sans-serif",
        transition: 'all 0.15s ease',
        color: 'inherit',
        font: 'inherit',
        WebkitAppearance: 'none',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = 'rgba(175,169,236,0.4)'
        if (!featured) e.currentTarget.style.background = 'rgba(255,255,255,0.10)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = featured ? 'rgba(175,169,236,0.2)' : 'rgba(255,255,255,0.10)'
        if (!featured) e.currentTarget.style.background = 'rgba(255,255,255,0.06)'
      }}
    >
      {/* Stacked date pill: MON DD / DAY / TIME */}
      <div style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        background: 'rgba(127,119,221,0.20)', borderRadius: 10,
        padding: '10px 8px', minWidth: 70, flexShrink: 0, gap: 2,
        border: '1px solid rgba(175,169,236,0.25)',
      }}>
        <span style={{ fontSize: 14, fontWeight: 700, color: '#fff', lineHeight: 1.1 }}>{monthDay}</span>
        <span style={{ fontSize: 10, color: '#AFA9EC', fontWeight: 600, letterSpacing: 0.5, lineHeight: 1 }}>{dayOfWeek}</span>
        {thru && (
          <span style={{ fontSize: 9, color: 'rgba(175,169,236,0.85)', fontWeight: 600, lineHeight: 1, marginTop: 1 }}>{thru}</span>
        )}
        {event.start_time && (
          <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.6)', fontWeight: 500, lineHeight: 1, marginTop: 2 }}>
            {time.hour}{time.period.toLowerCase()}
          </span>
        )}
      </div>
      
      {/* Title + venue + pills, wraps if needed */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          fontWeight: 600, fontSize: 14, color: '#fff',
          lineHeight: 1.3, marginBottom: 4,
          display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
          overflow: 'hidden',
        }}>
          {event.title}
        </div>
        {(event.venue_name || event.location) && (
          <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.55)', marginBottom: 4, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {event.venue_name || event.location}
            {event.price && <span style={{ color: (event.price || '').toLowerCase() === 'free' ? '#10b981' : '#EF9F27', marginLeft: 8, fontWeight: 600 }}>· {event.price}</span>}
            {event.is_free === true && !event.price && <span style={{ color: '#10b981', marginLeft: 8, fontWeight: 600 }}>· Free</span>}
            {event.is_free === false && <span style={{ color: '#f59e0b', marginLeft: 8, fontWeight: 600 }}>· Paid</span>}
          </div>
        )}
        {event.description && (
          <div style={{
            fontSize: 12, color: 'rgba(255,255,255,0.45)',
            marginBottom: 6, lineHeight: 1.4,
            display: '-webkit-box', WebkitLineClamp: 1, WebkitBoxOrient: 'vertical',
            overflow: 'hidden',
          }}>
            {event.description}
          </div>
        )}
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
          {(event.categories || []).slice(0, 3).map(c => <V2CategoryPill key={c} name={c} role="category" />)}
          {(event.facets || []).slice(0, 2).map(f => <V2CategoryPill key={f} name={f} role="facet" />)}
        </div>
      </div>
    </button>
  )
}

export function EventsV2Embedded({ cityKeyProp }: { cityKeyProp?: string } = {}) {
  const [events, setEvents] = useState<V2YocEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [dayFilter, setDayFilter] = useState<V2DayFilter>('today')
  const [timeFilter, setTimeFilter] = useState<V2TimeFilter>('any')
  const [activeCategory, setActiveCategory] = useState<string>('all')
  const [showAllCategories, setShowAllCategories] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedEvent, setSelectedEvent] = useState<EventModalData | null>(null)
  const [showResultsView, setShowResultsView] = useState(false)
  const [activeChips, setActiveChips] = useState<Set<ChipId>>(new Set())
  const [chipPickedDate, setChipPickedDate] = useState<string>('')
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const [showMoreFilters, setShowMoreFilters] = useState(false)
  // When chips are mutually exclusive (one date filter at a time). Vibe chips
  // stack. Pick-a-date is a When chip too.
  const WHEN_CHIPS: ReadonlyArray<ChipId> = ['weekend', 'today', 'tomorrow', 'next7', 'pickdate']
  const toggleChip = (id: ChipId) => {
    setDropdownOpen(true)
    setActiveChips(prev => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        // If this is a When chip, clear any other When chip first.
        if (WHEN_CHIPS.includes(id)) {
          for (const w of WHEN_CHIPS) next.delete(w)
        }
        next.add(id)
      }
      return next
    })
    // Tapping a non-pickdate When chip should also clear the picked date value.
    if (WHEN_CHIPS.includes(id) && id !== 'pickdate') setChipPickedDate('')
  }
  const searchInputRef = useRef<HTMLInputElement | null>(null)
  const pickDateInputRef = useRef<HTMLInputElement | null>(null)
  const suppressOutsideRef = useRef<number>(0)
  const [searchRect, setSearchRect] = useState<{top:number;left:number;width:number} | null>(null)
  const [mounted, setMounted] = useState(false)
  useEffect(() => { setMounted(true) }, [])
  useEffect(() => {
    if (!dropdownOpen) { setSearchRect(null); return }
    const update = () => {
      const r = searchInputRef.current?.getBoundingClientRect()
      if (!r) return
      // Never let the dropdown render above the site header (60px) — when the
      // user scrolls so the input goes off-screen, the dropdown clamps to just
      // below the header instead of overlapping it.
      setSearchRect({ top: r.bottom + 6, left: r.left, width: r.width })
    }
    update()
    window.addEventListener('resize', update)
    window.addEventListener('scroll', update, true)
    return () => {
      window.removeEventListener('resize', update)
      window.removeEventListener('scroll', update, true)
    }
  }, [dropdownOpen])

  const dropdownRef = useRef<HTMLDivElement | null>(null)
  useEffect(() => {
    if (!dropdownOpen) return
    const onMouseDown = (ev: MouseEvent) => {
      const t = ev.target as Node | null
      if (searchInputRef.current && t && searchInputRef.current.contains(t)) return
      if (dropdownRef.current && t && dropdownRef.current.contains(t)) return
      // Don't close while the event modal is open (user is interacting with it).
      if (selectedEvent) return
      // Native date picker lives outside our DOM; suppress outside-close
      // briefly after Pick-a-date opens, so picker interactions don't reset.
      if (Date.now() < suppressOutsideRef.current) return
      // Click outside = full reset: close dropdown AND clear all search state.
      setDropdownOpen(false)
      setSearchQuery('')
      setActiveChips(new Set())
      setChipPickedDate('')
      setShowMoreFilters(false)
    }
    document.addEventListener('mousedown', onMouseDown)
    const onKey = (ev: KeyboardEvent) => {
      if (ev.key === 'Escape') {
        if (selectedEvent) return
        setDropdownOpen(false)
        setSearchQuery('')
        setActiveChips(new Set())
        setChipPickedDate('')
        setShowMoreFilters(false)
        suppressOutsideRef.current = 0
      }
    }
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onMouseDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [dropdownOpen, selectedEvent])


  const [pickedDate, setPickedDate] = useState<string>(v2DateToStr(v2TodayMountain()))
  const [radius, setRadius] = useState<number>(10)
  const [locationMode, setLocationMode] = useState<'city' | 'mylocation' | 'zip'>('city')
  const [zipCode, setZipCode] = useState<string>('')
  const [userCoords, setUserCoords] = useState<{ lat: number; lng: number } | null>(null)
  const [cityKey, setCityKey] = useState<string>('parkcity')
  
  useEffect(() => {
    // Detect city from URL
    const params = new URLSearchParams(window.location.search)
    const cityKeyLocal = cityKeyProp || params.get('city') || 'parkcity'
    setCityKey(cityKeyLocal)
    const fileMap: Record<string, string> = {
      parkcity: '/events.json',
      heber: '/events-heber.json',
      jackson: '/events-jackson.json',
      elkhartlake: '/events-elkhartlake.json',
    }
    const file = fileMap[cityKeyLocal] || '/events.json'
    setLoading(true)
    fetch(file)
      .then(r => r.json())
      .then(d => {
        setEvents((d.events || d) as V2YocEvent[])
        setLoading(false)
      })
      .catch(e => {
        console.error('V2: failed to load events', e)
        setLoading(false)
      })
  }, [cityKeyProp])
  
  const filteredEvents = useMemo(() => {
    let result = events
    const today = v2TodayMountain()
    const todayStr = v2DateToStr(today)

    // An event "occurs on" a day if that day falls between its start date and
    // end_date (inclusive). Multi-day events (festivals like Song Summit) should
    // appear on every day they run, not just the first day.
    const occursOn = (e: V2YocEvent, dayStr: string): boolean => {
      const start = e.date || ''
      const end = e.end_date || start
      return start <= dayStr && dayStr <= end
    }
    const occursInRange = (e: V2YocEvent, rangeStart: string, rangeEnd: string): boolean => {
      const start = e.date || ''
      const end = e.end_date || start
      // Overlap test: event range intersects [rangeStart, rangeEnd]
      return start <= rangeEnd && end >= rangeStart
    }

    // Keep events that haven't fully ended yet (end_date >= today).
    result = result.filter(e => ((e.end_date || e.date) || '') >= todayStr)
    
    if (dayFilter === 'today') result = result.filter(e => occursOn(e, todayStr))
    else if (dayFilter === 'tomorrow') {
      const tom = new Date(today); tom.setDate(today.getDate() + 1)
      const tomStr = v2DateToStr(tom)
      result = result.filter(e => occursOn(e, tomStr))
    } else if (dayFilter === 'weekend') {
      const { start, end } = v2WeekendDates()
      result = result.filter(e => occursInRange(e, v2DateToStr(start), v2DateToStr(end)))
    } else if (dayFilter === '7days') {
      const week = new Date(today); week.setDate(today.getDate() + 7)
      result = result.filter(e => occursInRange(e, todayStr, v2DateToStr(week)))
    } else if (dayFilter === 'pickdate') {
      result = result.filter(e => occursOn(e, pickedDate))
    }
    
    if (timeFilter !== 'any') {
      result = result.filter(e => {
        const t = v2ParseTime12h(e.start_time)
        if (t === null) return true
        if (timeFilter === 'morning') return t < 12 * 60
        if (timeFilter === 'afternoon') return t >= 12 * 60 && t < 17 * 60
        if (timeFilter === 'evening') return t >= 17 * 60 && t < 21 * 60
        if (timeFilter === 'latenight') return t >= 21 * 60
        return true
      })
    }
    
    if (activeCategory !== 'all') {
      result = result.filter(e => (e.categories || []).includes(activeCategory))
    }
    


    // Radius filter: keep events within `radius` miles of the origin.
    // Origin is the user's GPS location if shared, else the city center.
    const origin = userCoords || CITY_CENTERS[cityKey] || CITY_CENTERS.parkcity
    if (origin) {
      result = result.filter(e => {
        // Events without coordinates are always kept (we can't measure them,
        // and dropping them would silently hide valid events).
        if (typeof e.lat !== 'number' || typeof e.lng !== 'number') return true
        const dist = v2DistanceMiles(origin.lat, origin.lng, e.lat, e.lng)
        return dist <= radius
      })
    }
    
    result.sort((a, b) => {
      if (a.date !== b.date) return (a.date || '').localeCompare(b.date || '')
      const ta = v2ParseTime12h(a.start_time) ?? 24 * 60
      const tb = v2ParseTime12h(b.start_time) ?? 24 * 60
      return ta - tb
    })
    return result
  }, [events, dayFilter, timeFilter, activeCategory, pickedDate, radius, userCoords, cityKey])

  const allUpcomingMatches = useMemo(() => {
    const q = searchQuery.trim().toLowerCase()
    const todayStr = v2DateToStr(v2TodayMountain())
    if (!q && activeChips.size === 0) return []
    return events
      .filter(e => ((e.end_date || e.date) || '') >= todayStr)
      .filter(e => matchesQuery(e, q))
      .filter(e => {
        for (const chip of activeChips) {
          if (!chipPassesEvent(chip, e, todayStr, chipPickedDate)) return false
        }
        return true
      })
      .sort((a, b) => (a.date || '').localeCompare(b.date || ''))
  }, [events, searchQuery, activeChips, chipPickedDate])
  
  // Featured events: things happening TODAY only. Manual flags first, then
  // today's best events ranked by tag richness. Empty if nothing today.
  const featuredEvents = useMemo(() => {
    // Featured follows the SELECTED day (the day shown in the header), not a
    // hardcoded "today" — otherwise navigating to June 1 still featured today's
    // events (and could surface a past event). Derive the viewed day from the
    // same day-filter state the main list uses.
    const dayStr = (() => {
      if (dayFilter === 'pickdate') return pickedDate
      const t = v2TodayMountain()
      if (dayFilter === 'tomorrow') t.setDate(t.getDate() + 1)
      // weekend / 7days / all / today all anchor on today for the featured pick
      return v2DateToStr(t)
    })()

    // Active on the selected day = day falls within event's date..end_date,
    // so a multi-day festival spanning that day counts.
    const activeOnDay = (e: any) => {
      const start = (e.date || '').slice(0, 10)
      const end = (e.end_date || start).slice(0, 10)
      return start <= dayStr && dayStr <= end
    }
    const richness = (e: any) => (e.categories?.length || 0) + (e.hook ? 2 : 0)
    const QUALITY_BAR = 2  // multiple categories, or a hook — a genuine standout

    const todayEvents = events.filter(activeOnDay)

    // Cap scales with how busy the day is: a quiet day shouldn't fill the strip,
    // a packed day can show more. This is a MAXIMUM — we still only show genuine
    // standouts up to it (never pad with filler).
    const n = todayEvents.length
    const MAX = n >= 11 ? 5 : n >= 5 ? 3 : 1

    // Manually-flagged events always lead (still capped by the tier).
    const manual = todayEvents.filter((e: any) => e.featured === true)
    if (manual.length >= MAX) return manual.slice(0, MAX)

    // Fill remaining slots with the day's genuine standouts (don't pad to MAX).
    const ranked = todayEvents
      .filter((e: any) => e.featured !== true)
      .sort((a, b) => richness(b) - richness(a) || (a.start_time || '').localeCompare(b.start_time || ''))
    const standouts = ranked.filter((e: any) => richness(e) >= QUALITY_BAR)

    const combined = [...manual, ...standouts].slice(0, MAX)

    // Never show an empty strip when the day has events: fall back to the
    // single best event of the day.
    if (combined.length === 0 && ranked.length > 0) return ranked.slice(0, 1)
    return combined
  }, [events, dayFilter, pickedDate])
  
  // Single day the user is viewing — only meaningful in single-day modes
  // (today/tomorrow/pickdate). In range modes (weekend/7days/all) we return ''
  // so cards badge each event's own date.
  const viewedDayStr = useMemo(() => {
    if (dayFilter === 'pickdate') return pickedDate
    if (dayFilter === 'today') return v2DateToStr(v2TodayMountain())
    if (dayFilter === 'tomorrow') {
      const t = v2TodayMountain(); t.setDate(t.getDate() + 1); return v2DateToStr(t)
    }
    return ''  // range modes: no single viewed day
  }, [dayFilter, pickedDate])

  const todayDow = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'][v2TodayMountain().getDay()]
  
  // Date range label that updates with the day filter
  const dateRangeLabel = useMemo(() => {
    const fmt = (d: Date) => d.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })
    const fmtShort = (d: Date) => d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
    const today = v2TodayMountain()
    if (dayFilter === 'today') return fmt(today)
    if (dayFilter === 'tomorrow') {
      const tom = new Date(today); tom.setDate(today.getDate() + 1)
      return fmt(tom)
    }
    if (dayFilter === 'weekend') {
      const { start, end } = v2WeekendDates()
      return `${fmtShort(start)} – ${fmtShort(end)}`
    }
    if (dayFilter === '7days') {
      const week = new Date(today); week.setDate(today.getDate() + 7)
      return `${fmtShort(today)} – ${fmtShort(week)}`
    }
    if (dayFilter === 'pickdate') {
      const parts = pickedDate.split('-')
      if (parts.length === 3) {
        const d = new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]))
        return fmt(d)
      }
      return pickedDate
    }
    return 'All upcoming'
  }, [dayFilter, pickedDate])
  
  // Shift day filter forward/back by N days. Sets to pickdate mode.
  const shiftDay = (delta: number) => () => {
    const base = (() => {
      if (dayFilter === 'today') return v2TodayMountain()
      if (dayFilter === 'tomorrow') {
        const t = v2TodayMountain(); t.setDate(t.getDate() + 1); return t
      }
      if (dayFilter === 'pickdate') {
        const parts = pickedDate.split('-')
        return new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]))
      }
      // For weekend/7days/all, anchor on today
      return v2TodayMountain()
    })()
    base.setDate(base.getDate() + delta)
    setPickedDate(v2DateToStr(base))
    setDayFilter('pickdate')
  }
  
  const handleEventClick = (ev: V2YocEvent) => {
    setSelectedEvent({
      title: ev.title, date: ev.date, end_date: ev.end_date,
      start_time: ev.start_time, end_time: ev.end_time,
      location: ev.venue_name || ev.location,
      description: ev.description, link: ev.link, source: ev.source,
      is_free: ev.is_free, price: ev.price, categories: ev.categories,
    })
  }
  
  return (
    <div style={{ fontFamily: "'DM Sans', sans-serif" }}>
      {/* Radius / Location bar */}
      <div style={{
        background: 'rgba(255,255,255,0.04)',
        border: '1px solid rgba(255,255,255,0.10)',
        borderRadius: 16, padding: '14px 18px', marginBottom: 12,
        display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap',
        position: 'relative', zIndex: 30,
      }}>
        <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.65)', fontWeight: 600, minWidth: 56 }}>Where:</span>
        <button
          onClick={() => {
            if (navigator.geolocation) {
              navigator.geolocation.getCurrentPosition(
                (pos) => {
                  setUserCoords({ lat: pos.coords.latitude, lng: pos.coords.longitude })
                  setLocationMode('mylocation')
                },
                (err) => console.error('Location error:', err)
              )
            }
          }}
          style={{
            padding: '6px 14px', fontSize: 13, borderRadius: 999,
            background: locationMode === 'mylocation' ? '#534AB7' : 'rgba(255,255,255,0.06)',
            color: '#fff',
            border: locationMode === 'mylocation' ? '1px solid transparent' : '1px solid rgba(255,255,255,0.18)',
            cursor: 'pointer', fontFamily: "'DM Sans', sans-serif",
          }}
        >📍 Use my location</button>
        <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.4)' }}>or</span>
        <div style={{ width: 220 }}>
          <CitySearch placeholder="City or ZIP — switch town" variant="compact" />
        </div>
        <div style={{ flex: 1, minWidth: 200, display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.65)', fontWeight: 600 }}>Radius:</span>
          <input
            type="range"
            min={1} max={50} step={1}
            value={radius}
            onChange={(e) => setRadius(Number(e.target.value))}
            style={{ flex: 1, accentColor: '#7F77DD', minWidth: 100 }}
          />
          <span style={{ fontSize: 13, color: '#fff', fontWeight: 600, minWidth: 50, textAlign: 'right' }}>{radius} mi</span>
          <span style={{
            fontSize: 13, fontWeight: 700, color: '#fff', whiteSpace: 'nowrap',
            background: '#534AB7', padding: '5px 12px', borderRadius: 999, marginLeft: 4,
          }}>{filteredEvents.length} event{filteredEvents.length !== 1 ? 's' : ''}</span>
        </div>
      </div>
      
      {/* Search + filter chips */}
      <div style={{
        background: 'rgba(255,255,255,0.04)',
        border: '1px solid rgba(255,255,255,0.10)',
        borderRadius: 16, padding: 18, marginBottom: 18,
        backdropFilter: 'blur(8px)',
      }}>
        <div style={{ position: 'relative', marginBottom: 16 }}>
          <input
            ref={searchInputRef}
            type="text"
            placeholder="Search bands, venues, or what to do..."
            value={searchQuery}
            onChange={(e) => { setSearchQuery(e.target.value); setDropdownOpen(true) }}
            onFocus={() => setDropdownOpen(true)}
            style={{
              width: '100%', padding: '11px 16px', fontSize: 14,
              border: '1px solid rgba(255,255,255,0.18)', borderRadius: 10,
              color: '#fff', boxSizing: 'border-box',
              background: 'rgba(255,255,255,0.06)',
              outline: 'none',
            }}
            className="v2-search-input"
          />
          {mounted && searchRect && dropdownOpen && createPortal((
            <div ref={dropdownRef} style={{
              position: 'fixed', top: searchRect.top, left: searchRect.left, width: searchRect.width,
              background: '#221a3a', border: '1px solid rgba(255,255,255,0.12)',
              borderRadius: 12, zIndex: 50, overflow: 'hidden',
              boxShadow: '0 12px 40px rgba(0,0,0,0.4)',
            }}>
              {/* Quick filter chips */}
              <div style={{
                padding: '10px 14px', borderBottom: '1px solid rgba(255,255,255,0.06)',
                background: 'rgba(127,119,221,0.05)',
                display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center',
              }}>
                {([
                  {id: 'weekend' as ChipId, label: 'This weekend'},
                  {id: 'today' as ChipId, label: 'Today'},
                  {id: 'tomorrow' as ChipId, label: 'Tomorrow'},
                ]).map(c => {
                  const active = activeChips.has(c.id)
                  return (
                    <button key={c.id} type="button" onClick={() => toggleChip(c.id)}
                      style={{
                        background: active ? '#534AB7' : 'rgba(255,255,255,0.08)',
                        color: active ? '#fff' : 'rgba(255,255,255,0.78)',
                        border: active ? '1px solid transparent' : '1px solid rgba(255,255,255,0.12)',
                        borderRadius: 999, padding: '4px 11px', fontSize: 11,
                        fontWeight: active ? 500 : 400, cursor: 'pointer',
                        fontFamily: 'inherit',
                      }}>{c.label}</button>
                  )
                })}
                <button type="button"
                  onClick={() => {
                    const inp = pickDateInputRef.current
                    if (!inp) return
                    // Suppress outside-close for 30 seconds while user
                    // navigates the native picker (months, year, day).
                    suppressOutsideRef.current = Date.now() + 60000
                    if (typeof inp.showPicker === 'function') {
                      try { inp.showPicker() } catch { inp.focus(); inp.click() }
                    } else {
                      inp.focus(); inp.click()
                    }
                  }}
                  style={{
                    background: activeChips.has('pickdate') ? '#534AB7' : 'rgba(255,255,255,0.08)',
                    color: activeChips.has('pickdate') ? '#fff' : 'rgba(255,255,255,0.78)',
                    border: activeChips.has('pickdate') ? '1px solid transparent' : '1px solid rgba(255,255,255,0.12)',
                    borderRadius: 999, padding: '4px 11px', fontSize: 11,
                    cursor: 'pointer', fontFamily: 'inherit',
                  }}>
                  {chipPickedDate && activeChips.has('pickdate') ? chipPickedDate : 'Pick a date'}
                </button>
                <input
                  ref={pickDateInputRef}
                  type="date"
                  value={chipPickedDate}
                  onChange={(e) => {
                    const v = e.target.value
                    setChipPickedDate(v)
                    setActiveChips(prev => {
                      const next = new Set(prev)
                      // Picking a date is a When choice — clear other When chips.
                      for (const w of ['weekend','today','tomorrow','next7'] as ChipId[]) next.delete(w)
                      if (v) next.add('pickdate'); else next.delete('pickdate')
                      return next
                    })
                    suppressOutsideRef.current = 0
                  }}
                  style={{ position: 'absolute', opacity: 0, width: 0, height: 0, padding: 0, border: 0, pointerEvents: 'none' }}
                />
                {(activeChips.size > 0 || searchQuery.trim()) && (
                  <button type="button"
                    onClick={() => {
                      setSearchQuery('')
                      setActiveChips(new Set())
                      setChipPickedDate('')
                      setShowMoreFilters(false)
                      setDropdownOpen(false)
                    }}
                    style={{
                      background: 'rgba(255,255,255,0.04)',
                      color: 'rgba(255,255,255,0.6)',
                      border: '1px solid rgba(255,255,255,0.10)',
                      borderRadius: 999, padding: '4px 11px', fontSize: 11,
                      cursor: 'pointer', fontFamily: 'inherit',
                    }}>Clear filters</button>
                )}
                <button type="button"
                  onClick={() => setShowMoreFilters(v => !v)}
                  style={{
                    background: 'transparent',
                    color: '#AFA9EC',
                    border: '1px dashed rgba(127,119,221,0.4)',
                    borderRadius: 999, padding: '4px 11px', fontSize: 11,
                    cursor: 'pointer', fontFamily: 'inherit',
                  }}>{showMoreFilters ? '− Less filters' : '+ More filters'}</button>
              </div>
              {showMoreFilters && (
                <div style={{
                  padding: '10px 14px', borderBottom: '1px solid rgba(255,255,255,0.06)',
                  background: 'rgba(127,119,221,0.03)',
                }}>
                  <div style={{
                    fontSize: 10, color: 'rgba(255,255,255,0.5)', fontWeight: 600,
                    letterSpacing: 0.5, textTransform: 'uppercase', marginBottom: 6,
                  }}>More when</div>
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 10 }}>
                    {([
                      {id: 'next7' as ChipId, label: 'Next 7 days'},
                    ]).map(c => {
                      const active = activeChips.has(c.id)
                      return (
                        <button key={c.id} type="button" onClick={() => toggleChip(c.id)}
                          style={{
                            background: active ? '#534AB7' : 'rgba(255,255,255,0.08)',
                            color: active ? '#fff' : 'rgba(255,255,255,0.78)',
                            border: active ? '1px solid transparent' : '1px solid rgba(255,255,255,0.12)',
                            borderRadius: 999, padding: '4px 11px', fontSize: 11,
                            fontWeight: active ? 500 : 400, cursor: 'pointer',
                            fontFamily: 'inherit',
                          }}>{c.label}</button>
                      )
                    })}
                  </div>
                  <div style={{
                    fontSize: 10, color: 'rgba(255,255,255,0.5)', fontWeight: 600,
                    letterSpacing: 0.5, textTransform: 'uppercase', marginBottom: 6,
                  }}>Vibe</div>
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {([
                      {id: 'music' as ChipId, label: 'Music'},
                      {id: 'outdoors' as ChipId, label: 'Outdoors'},
                      {id: 'food' as ChipId, label: 'Food & Drink'},
                      {id: 'family' as ChipId, label: 'Family'},
                      {id: 'arts' as ChipId, label: 'Arts'},
                      {id: 'sports' as ChipId, label: 'Sports'},
                      {id: 'kids' as ChipId, label: 'Kids'},
                      {id: 'wellness' as ChipId, label: 'Wellness'},
                      {id: 'education' as ChipId, label: 'Education'},
                      {id: 'festivals' as ChipId, label: 'Festivals'},
                    ]).map(c => {
                      const active = activeChips.has(c.id)
                      return (
                        <button key={c.id} type="button" onClick={() => toggleChip(c.id)}
                          style={{
                            background: active ? '#534AB7' : 'rgba(255,255,255,0.08)',
                            color: active ? '#fff' : 'rgba(255,255,255,0.78)',
                            border: active ? '1px solid transparent' : '1px solid rgba(255,255,255,0.12)',
                            borderRadius: 999, padding: '4px 11px', fontSize: 11,
                            fontWeight: active ? 500 : 400, cursor: 'pointer',
                            fontFamily: 'inherit',
                          }}>{c.label}</button>
                      )
                    })}
                  </div>
                </div>
              )}
              {allUpcomingMatches.slice(0, 5).map((ev, i) => {
                const d = v2ParseEventDate((ev.date || '').slice(0, 10))
                const MON = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
                const DOW = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat']
                const datePill = d ? `${DOW[d.getDay()]} ${MON[d.getMonth()]} ${d.getDate()}` : ''
                return (
                  <div
                    key={`sr-${i}`}
                    onClick={() => { handleEventClick(ev) }}
                    style={{
                      padding: '12px 16px',
                      borderBottom: '1px solid rgba(255,255,255,0.06)',
                      display: 'flex', alignItems: 'center', gap: 12,
                      cursor: 'pointer',
                    }}
                  >
                    <div style={{
                      background: '#534AB7', color: '#fff',
                      borderRadius: 8, padding: '4px 8px',
                      fontSize: 11, fontWeight: 500, minWidth: 64, textAlign: 'center',
                      flexShrink: 0,
                    }}>{datePill}</div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{
                        color: '#fff', fontSize: 14, fontWeight: 500,
                        whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                      }}>{ev.title}</div>
                      <div style={{
                        color: 'rgba(255,255,255,0.55)', fontSize: 12,
                        whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                      }}>{ev.venue_name || ev.location || ev.source || ''}</div>
                    </div>
                  </div>
                )
              })}
              {allUpcomingMatches.length > 5 && (
                <div
                  onClick={() => setShowResultsView(true)}
                  style={{
                    padding: '12px 16px', textAlign: 'center',
                    color: '#AFA9EC', fontSize: 12, cursor: 'pointer',
                    background: 'rgba(127,119,221,0.05)', fontWeight: 500,
                  }}
                >See all {allUpcomingMatches.length} results &rarr;</div>
              )}
            </div>
          ), document.body)}
          
        </div>
        <div style={{ display: 'flex', gap: 6, marginBottom: 12, overflowX: 'auto', alignItems: 'center' }}>
          <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.65)', minWidth: 56, fontWeight: 600 }}>When:</span>
          <V2Chip active={dayFilter === 'all'} onClick={() => setDayFilter('all')}>All upcoming</V2Chip>
          <V2Chip active={dayFilter === 'today'} onClick={() => setDayFilter('today')}>Today · {todayDow}</V2Chip>
          <V2Chip active={dayFilter === 'tomorrow'} onClick={() => setDayFilter('tomorrow')}>Tomorrow</V2Chip>
          <V2Chip active={dayFilter === 'weekend'} onClick={() => setDayFilter('weekend')}>This weekend</V2Chip>
          <V2Chip active={dayFilter === '7days'} onClick={() => setDayFilter('7days')}>Next 7 days</V2Chip>
          <V2Chip active={dayFilter === 'pickdate'} onClick={() => setDayFilter('pickdate')}>Pick date</V2Chip>
          {dayFilter === 'pickdate' && (
            <input type="date" value={pickedDate} onChange={(e) => setPickedDate(e.target.value)}
              style={{ padding: '6px 10px', fontSize: 13, borderRadius: 8, border: '1px solid rgba(83,74,183,0.18)' }}
            />
          )}
        </div>
        <div style={{ display: 'flex', gap: 6, marginBottom: 12, overflowX: 'auto', alignItems: 'center' }}>
          <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.65)', minWidth: 56, fontWeight: 600 }}>Time:</span>
          <V2Chip compact active={timeFilter === 'any'} onClick={() => setTimeFilter('any')}>Any time</V2Chip>
          <V2Chip compact active={timeFilter === 'morning'} onClick={() => setTimeFilter('morning')}>Morning</V2Chip>
          <V2Chip compact active={timeFilter === 'afternoon'} onClick={() => setTimeFilter('afternoon')}>Afternoon</V2Chip>
          <V2Chip compact active={timeFilter === 'evening'} onClick={() => setTimeFilter('evening')}>Evening</V2Chip>
          <V2Chip compact active={timeFilter === 'latenight'} onClick={() => setTimeFilter('latenight')}>Late night</V2Chip>
        </div>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
          <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.65)', minWidth: 56, fontWeight: 600 }}>Vibe:</span>
          <V2Chip compact active={activeCategory === 'all'} onClick={() => setActiveCategory('all')}>All categories</V2Chip>
          {V2_ALL_CATEGORIES.map(cat => (
            <V2Chip key={cat} compact active={activeCategory === cat}
              onClick={() => setActiveCategory(cat)}
              color={activeCategory === cat ? V2_CATEGORY_COLORS[cat] : undefined}
            >{cat}</V2Chip>
          ))}
        </div>
      </div>
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr auto 1fr',
        alignItems: 'center',
        margin: '12px 4px 20px',
      }}>
        <div /> {/* left spacer */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, justifyContent: 'center' }}>
          <button onClick={shiftDay(-1)} style={{
            background: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.18)',
            color: '#fff', width: 36, height: 36, borderRadius: '50%',
            fontSize: 18, cursor: 'pointer', lineHeight: 1,
          }} title="Previous day">‹</button>
          <div style={{
            fontSize: 22, fontWeight: 600, color: '#fff',
            fontFamily: "'DM Serif Display', serif", minWidth: 280, textAlign: 'center',
          }}>
            {dateRangeLabel}
          </div>
          <button onClick={shiftDay(1)} style={{
            background: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.18)',
            color: '#fff', width: 36, height: 36, borderRadius: '50%',
            fontSize: 18, cursor: 'pointer', lineHeight: 1,
          }} title="Next day">›</button>
        </div>
        <div style={{
          fontSize: 22, fontWeight: 600, color: '#fff',
          fontFamily: "'DM Serif Display', serif", textAlign: 'right',
        }}>
          {filteredEvents.length} event{filteredEvents.length !== 1 ? 's' : ''}
        </div>
      </div>
      {/* Featured events orange band */}
      {featuredEvents.length > 0 && (
        <div style={{
          background: 'linear-gradient(135deg, #FAEEDA 0%, #FCD9A8 50%, #FAEEDA 100%)',
          padding: '24px 20px',
          borderRadius: 16,
          margin: '0 0 24px',
          border: '1px solid rgba(239,159,39,0.5)',
          boxShadow: '0 4px 20px rgba(239,159,39,0.25)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
            <div style={{
              display: 'inline-flex', alignItems: 'center', gap: 6,
              background: '#EF9F27', color: 'white',
              padding: '5px 14px', borderRadius: 100,
              fontSize: 11, fontWeight: 700, letterSpacing: 0.5,
              textTransform: 'uppercase',
            }}>★ Featured</div>
            <span style={{ fontSize: 12, color: 'rgba(154,52,18,0.85)', fontWeight: 600 }}>
              {viewedDayStr === v2DateToStr(v2TodayMountain()) ? 'Happening today' : `Happening ${dateRangeLabel}`}
            </span>
          </div>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(440px, 1fr))',
            gap: 8,
          }}>
            {featuredEvents.map((ev, i) => (
              <V2EventCard key={`featured-${ev.title}-${ev.date}-${i}`} event={ev} onClick={() => handleEventClick(ev)} featured viewedDay={viewedDayStr} />
            ))}
          </div>
        </div>
      )}
      
      {loading ? (
        <div style={{ textAlign: 'center', padding: 60, color: '#6b6880' }}>Loading events...</div>
      ) : filteredEvents.length === 0 ? (
        <div style={{ textAlign: 'center', padding: 60, color: '#6b6880', background: '#fff', borderRadius: 14, border: '1px solid rgba(83,74,183,0.12)' }}>
          No events match your filters. Try widening the time range or clearing search.
        </div>
      ) : (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(440px, 1fr))',
          gap: 8,
        }}>
          {filteredEvents.map((ev, i) => (
            <V2EventCard key={`${ev.title}-${ev.date}-${i}`} event={ev} onClick={() => handleEventClick(ev)} viewedDay={viewedDayStr} />
          ))}
        </div>
      )}
      <EventModal event={selectedEvent} onClose={() => setSelectedEvent(null)} />
    </div>
  )
}

declare global {
  interface Window {
    L: any
    google: any
    setView: (v: string) => void
    switchCity: (k: string, el: any) => void
    useMyLocation: () => void
    heroUseMyLocation: () => void
    clearHeroLocation: () => void
    jumpToToday: () => void
    onRadiusChange: (v: string) => void
    clearRadius: () => void
    openEventModal: (card: HTMLElement) => void
    closeEventModal: () => void
    openAtcDropdown: (e: Event, btn: HTMLElement) => void
    openAtcFromModal: () => void
    openShareMenu: (e: Event) => void
    closeShareMenu: () => void
    copyShareLink: (e: Event) => void
    eyebrowSwitchCity: (e: Event, k: string) => void
    toggleEyebrowDropdown: (e: Event) => void
    initPlacesAutocomplete: () => void
    userLat: number | null
  }
}

export default function CalendarClient() {
  const searchParams = useSearchParams()
  const cityDisplayName = (() => {
    const k = searchParams.get('city') || 'parkcity'
    const names: Record<string, string> = {
      parkcity: 'Park City', heber: 'Heber Valley',
      jackson: 'Jackson Hole', elkhartlake: 'Elkhart Lake',
    }
    return names[k] || 'Local'
  })()

  // Scroll reveal observer — runs even in V2 mode so reveal sections become visible.
  useEffect(() => {
    const reveals = document.querySelectorAll('.reveal')
    const revealObserver = new IntersectionObserver((entries) => {
      entries.forEach((e, i) => {
        if (e.isIntersecting) {
          setTimeout(() => e.target.classList.add('visible'), i * 80)
          revealObserver.unobserve(e.target)
        }
      })
    }, { threshold: 0.1 })
    reveals.forEach(el => revealObserver.observe(el))
    return () => revealObserver.disconnect()
  }, [])

  useEffect(() => {
    // ── All initialization JavaScript ──
    // This is the full calendar app logic, adapted from the original index.html.
    // EARLY BAIL: V2 calendar widget replaces the imperative DOM portion.
    // If the legacy DOM elements aren't present, skip all the old logic.
    if (!document.getElementById('cal-events-container')) {
      return  // V2 calendar is active — skip legacy DOM manipulation
    }

    const DAYS = ['SUN','MON','TUE','WED','THU','FRI','SAT']
    const MONTHS_FULL = ['January','February','March','April','May','June','July','August','September','October','November','December']
    const today = new Date()
    let allEvents: any[] = []

    const container = document.getElementById('cal-events-container')!
    const noResults = document.getElementById('no-results')!
    const dateLabel = document.querySelector('.calendar-section p') as HTMLElement
    const searchInput = document.getElementById('event-search') as HTMLInputElement
    const searchClear = document.getElementById('search-clear') as HTMLButtonElement
    const dayContainer = document.getElementById('cal-days-container')!

    let activeDate: Date = today
    let activeCategory = 'all'
    let activeSearch = ''
    let showAllDates = false
    let weekOffset = 0
    let selectedDate = new Date(today)
    let pickerDate = new Date(today.getFullYear(), today.getMonth(), 1)
    let dailyFeaturedTitle: string | null = null
    let userLat: number | null = null
    let userLng: number | null = null
    let radiusMiles = 25
    let radiusActive = false
    let currentCity = 'parkcity'
    let currentView = 'list'
    let map: any = null
    let mapMarkers: any[] = []
    let modalCardRef: HTMLElement | null = null
    let zipTimer: ReturnType<typeof setTimeout> | null = null

    window.userLat = null

    const CITY_CENTERS: Record<string, { center: [number, number]; zoom: number }> = {
      parkcity: { center: [40.6461, -111.4980], zoom: 12 },
      elkhartlake: { center: [43.8358, -88.0051], zoom: 13 },
      heber: { center: [40.5071, -111.4133], zoom: 12 },
      jackson: { center: [43.4799, -110.7624], zoom: 11 },
    }

    const CITIES: Record<string, any> = {
      parkcity: {
        name: 'Park City, UT', label: 'Park City & Summit County',
        file: 'events.json', supplementalFile: 'events-heber.json',
        aboutLabel: 'About Park City', aboutPage: '/about/park-city',
        junk: ['not just a ski town', 'summer hiking', 'treat yourself', 'shopping', 'previous month', 'next month'],
      },
      elkhartlake: {
        name: 'Elkhart Lake, WI', label: 'Elkhart Lake & Sheboygan County',
        file: 'events-elkhartlake.json',
        aboutLabel: 'About Elkhart Lake', aboutPage: '/about/elkhart-lake',
        junk: ['previous month', 'next month'],
      },
      heber: {
        name: 'Heber Valley, UT', label: 'Heber Valley & Wasatch County',
        file: 'events-heber.json',
        aboutLabel: 'About Heber', aboutPage: '/about/heber',
        junk: ['previous month', 'next month'],
      },
      jackson: {
        name: 'Jackson Hole, WY', label: 'Jackson Hole & Teton County',
        file: 'events-jackson.json',
        aboutLabel: 'About Jackson Hole', aboutPage: '/about/jackson-hole',
        junk: ['previous month', 'next month'],
      },
    }

    const VENUE_COORDS: Record<string, [number, number]> = {
      'egyptian theatre': [40.6454, -111.4978], 'spur bar': [40.6449, -111.4972],
      'the spur': [40.6449, -111.4972], 'high west': [40.6441, -111.4976],
      'no name saloon': [40.6448, -111.4970], 'park city library': [40.6494, -111.5013],
      'kimball junction': [40.6897, -111.5430], 'swaner': [40.6897, -111.5430],
      'deer valley': [40.6374, -111.4783], 'snowbird': [40.5830, -111.6559],
      'park city mountain': [40.6516, -111.5080], 'jordanelle': [40.6000, -111.4280],
      'heber': [40.5069, -111.4133], 'kimball arts': [40.6451, -111.4976],
      'old town': [40.6449, -111.4972], 'main street': [40.6449, -111.4972],
    }

    const ZIP_COORDS: Record<string, [number, number]> = {
      '84060': [40.6461, -111.4979], '84068': [40.6461, -111.4979],
      '84098': [40.7021, -111.5423], '84032': [40.5069, -111.4133],
      '53020': [43.8352, -87.9710], '53073': [43.7447, -87.9773],
      '53081': [43.7508, -87.7145],
    }

    function dateToStr(d: Date): string {
      return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`
    }

    const months: Record<string, string> = {jan:'01',feb:'02',mar:'03',apr:'04',may:'05',jun:'06',jul:'07',aug:'08',sep:'09',oct:'10',nov:'11',dec:'12'}

    function parseDate(dateStr: string): string | null {
      if (!dateStr || dateStr === 'See website') return null
      let s = dateStr.toLowerCase().replace(/[–—]/g, '-').replace(/[,.]/g, '').trim()
      if (s.length > 60) return null
      let m: RegExpMatchArray | null
      m = s.match(/^(\d{4})-(\d{2})-(\d{2})/)
      if (m) return `${m[1]}-${m[2]}-${m[3]}`
      m = s.match(/^([a-z]{3,})(\d{1,2})$/)
      if (m) { const mo = months[m[1].slice(0,3)]; if (mo) return `2026-${mo}-${m[2].padStart(2,'0')}` }
      m = s.match(/([a-z]{3,})\s+(\d{1,2})(?:\s+(\d{4}))?/)
      if (m) { const mo = months[m[1].slice(0,3)]; const yr = m[3] || '2026'; if (mo) return `${yr}-${mo}-${m[2].padStart(2,'0')}` }
      return null
    }

    function parseEndDate(dateStr: string): string | null {
      if (!dateStr) return null
      const s = dateStr.toLowerCase().replace(/[–—]/g, '-').replace(/[,.]/g, '').trim()
      const parts = s.split(/\s*-\s*/)
      if (parts.length >= 2) {
        const last = parts[parts.length - 1].trim()
        let m: RegExpMatchArray | null = last.match(/^(\d{4})-(\d{2})-(\d{2})/)
        if (m) return `${m[1]}-${m[2]}-${m[3]}`
        m = last.match(/([a-z]{3,})\s*(\d{1,2})(?:\s+(\d{4}))?/)
        if (m) { const mo = months[m[1].slice(0,3)]; const yr = m[3] || '2026'; if (mo) return `${yr}-${mo}-${m[2].padStart(2,'0')}` }
      }
      return null
    }

    function getVenueCoords(location: string): [number,number] | null {
      if (!location) return null
      const loc = location.toLowerCase()
      for (const [venue, coords] of Object.entries(VENUE_COORDS)) { if (loc.includes(venue)) return coords }
      return null
    }

    function distanceMilesFromUser(lat1: number, lng1: number, lat2: number, lng2: number): number {
      const R = 3958.8
      const dLat = (lat2-lat1)*Math.PI/180
      const dLng = (lng2-lng1)*Math.PI/180
      const a = Math.sin(dLat/2)**2 + Math.cos(lat1*Math.PI/180)*Math.cos(lat2*Math.PI/180)*Math.sin(dLng/2)**2
      return R*2*Math.atan2(Math.sqrt(a), Math.sqrt(1-a))
    }

    function distanceMilesFromPC(lat: number, lng: number): number {
      return distanceMilesFromUser(40.6461, -111.4980, lat, lng)
    }

    function getCategories(event: any): string {
      const text = ((event.title||'')+' '+(event.description||'')).toLowerCase()
      const location = (event.location||'').toLowerCase()
      const cats: string[] = []
      if (/music|concert|band|jazz|live|perform|sing|song|dj|bluegrass|acoustic|folk|rock|country|reggae|blues|indie/.test(text)) cats.push('music')
      if (/hike|trail|outdoor|bike|ski|snow|mountain|park|nature|climb|kayak|paddle|snowshoe|camp/.test(text)) cats.push('outdoor')
      if (/food|drink|wine|beer|cocktail|dine|eat|taste|market|farm|chef|brewery|distill|whiskey|spirits|brunch/.test(text)) cats.push('food')
      if (/art|gallery|exhibit|museum|paint|sculpt|craft|film|theatre|theater|show|play|dance|screening|improv/.test(text)) cats.push('arts')
      if (/run|race|marathon|5k|10k|triathlon|relay|cycling|fitness|gym|yoga|pilates|workout|athletic/.test(text)) cats.push('sports')
      if (/kid|child|family|youth|teen|school|junior|baby|parent|preschool|storytime|story time/.test(text)) cats.push('family')
      if (/wellness|meditat|breathwork|sound|healing|spa|health|therapy|mindful/.test(text)) cats.push('wellness')
      if (/community|nonprofit|charity|volunteer|fundrais|lecture|talk|class|learn|workshop|meeting/.test(text)) cats.push('community')
      const MUSIC_VENUES = ['spur bar','spur and grill','the spur','side door']
      const FOOD_VENUES = ['high west','no name saloon','handle','riverhorse','vessel']
      const OUTDOOR_VENUES = ['swaner','round valley','trail','mountain','resort','jordanelle','deer valley']
      const ARTS_VENUES = ['egyptian','kimball arts','library','museum','gallery','eccles','sundance']
      const FAMILY_VENUES = ['library','recreation center','fieldhouse','ice arena','basin rec']
      if (MUSIC_VENUES.some(v => location.includes(v))) cats.push('music')
      if (FOOD_VENUES.some(v => location.includes(v))) cats.push('food')
      if (OUTDOOR_VENUES.some(v => location.includes(v))) cats.push('outdoor')
      if (ARTS_VENUES.some(v => location.includes(v)||text.includes(v))) cats.push('arts')
      if (FAMILY_VENUES.some(v => location.includes(v))) cats.push('family')
      if (['egyptian theatre','park city institute'].some(v => location.includes(v)||text.includes(v))) cats.push('paid')
      if (event.source === 'Running in the USA') cats.push('sports')
      if (event.is_free === true) cats.push('free')
      else if (event.is_free === false) cats.push('paid')
      else if (/\bfree\b/.test(text)) cats.push('free')
      else if (/\$\d|\bticket(s)?\b|\bcost\b|\bfee\b/.test(text)) cats.push('paid')
      return [...new Set(cats)].join(' ') || 'community'
    }

    function getDailyFeaturedTitle(forDate?: Date): string | null {
      const d = forDate || new Date()
      const start = new Date(d.getFullYear(), 0, 0)
      const dayOfYear = Math.floor((d.getTime() - start.getTime()) / 86400000)
      const dateStr = dateToStr(d)
      const pool = allEvents.filter(e => e.date?.slice(0,10) === dateStr && e.featured !== true && e.source !== 'Running in the USA' && !(e.title||'').toLowerCase().includes('festival'))
      const seen = new Set<string>()
      const unique = pool.filter(e => { if (seen.has(e.title)) return false; seen.add(e.title); return true }).sort((a,b) => a.title.localeCompare(b.title))
      if (!unique.length) return null
      return unique[dayOfYear % unique.length].title
    }

    function isFeaturedEvent(event: any): boolean {
      return event.featured === true || event.source === 'Running in the USA' || (event.title||'').toLowerCase().includes('festival') || (dailyFeaturedTitle !== null && event.title === dailyFeaturedTitle)
    }

    function renderEvent(event: any, overrideDisplayDate?: string | null): string {
      const cats = getCategories(event)
      const startDate = parseDate(event.date)
      const endDate = event.end_date ? parseDate(event.end_date) : (parseEndDate(event.date) || startDate)
      const monthNames = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
      let displayMonth = 'See', displayDay = 'site'
      const displayDateStr = overrideDisplayDate || startDate
      if (displayDateStr) {
        const parts = displayDateStr.split('-')
        displayMonth = monthNames[parseInt(parts[1])-1]
        displayDay = String(parseInt(parts[2]))
        // (Multi-day events no longer show a '+' after the day number)
      }
      const source = event.source || 'Local'
      const sourceShort = source.replace('Visit Park City','visitparkcity.com').replace('KPCW Community Calendar','KPCW').replace('Running in the USA','runningintheusa.com').replace('The Park Record','Park Record').replace('Google Events','Google')
      const catList = cats.split(' ').filter(Boolean)
      const tagMap: Record<string, [string,string]> = { music:['t-music','Music'], outdoor:['t-outdoor','Outdoor'], food:['t-food','Food & Drink'], arts:['t-arts','Arts'], sports:['t-sports','Sports'], family:['t-family','Family'], wellness:['t-community','Wellness'], community:['t-community','Community'], free:['t-free','Free'], paid:['t-paid','Paid'] }
      const tagHTML = catList.slice(0,3).map((c:string) => { const t = tagMap[c]; return t ? `<span class="cal-tag ${t[0]}">${t[1]}</span>` : '' }).join('')
      const venueCoords = getVenueCoords(event.location)
      const lat = event.lat || (venueCoords && venueCoords[0])
      const lng = event.lng || (venueCoords && venueCoords[1])
      let distLabel = ''
      if (radiusActive && userLat && userLng && lat && lng) {
        const d = distanceMilesFromUser(userLat, userLng, lat, lng)
        if (d > 0.5) distLabel = ` · ${Math.round(d*10)/10} mi`
      } else if (lat && lng) {
        const d = distanceMilesFromPC(lat, lng)
        if (d > 0.5) distLabel = ` · ${Math.round(d*10)/10} mi`
      }
      const featured = isFeaturedEvent(event)
      const startStr = startDate || ''
      const endStr = endDate || startStr
      return `<div class="cal-event${featured?' featured':''}" data-categories="${cats}" data-start="${startStr}" data-end="${endStr}" data-recurrence="${event.recurrence||''}" data-recurrence-day="${event.recurrence_day||''}" data-recurrence-days="${event.recurrence_days||''}" data-lat="${event.lat||''}" data-lng="${event.lng||''}" data-title="${(event.title||'').replace(/"/g,'&quot;')}" data-location="${(event.location||'').replace(/"/g,'&quot;')}" data-address="${(event.address||'').replace(/"/g,'&quot;')}" data-venue-name="${(event.venue_name||'').replace(/"/g,'&quot;')}" data-date="${event.date||''}" data-end-date="${event.end_date||''}" data-link="${event.link||''}" data-description="${(event.description||'').replace(/"/g,'&quot;').replace(/\n/g,' ')}" data-source="${sourceShort}" data-start-time="${event.start_time||''}" data-end-time="${event.end_time||''}" onclick="openEventModal(this)" style="cursor:pointer"><div class="cal-event-time"><div class="h">${displayMonth}</div><div class="ap">${displayDay}</div>${event.start_time?`<div style="font-size:9px;color:white;margin-top:3px;white-space:nowrap">${event.start_time}${event.end_time?"–"+event.end_time:""}</div>`:''}</div><div class="cal-event-info"><h4>${event.title}</h4><p>${(event.description||'').slice(0,120)||'See website for details.'}</p><div class="cal-tags">${tagHTML}<span class="cal-source">via ${sourceShort}${distLabel}</span></div></div><div class="cal-event-actions"><button class="atc-btn" title="Add to calendar" onclick="openAtcDropdown(event,this)">📅</button></div></div>`
    }

    function applyFilters() {
      const selDateStr = showAllDates ? null : dateToStr(activeDate)
      dailyFeaturedTitle = getDailyFeaturedTitle(activeDate)
      const dayNames = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday']

      const visible = allEvents.filter(event => {
        if (!showAllDates) {
          const s = parseDate(event.date)
          const en = event.end_date ? parseDate(event.end_date) : s
          if (!s) return false
          if (selDateStr! < s || selDateStr! > (en || s)) return false
          const todayName = dayNames[activeDate.getDay()]
          if (event.recurrence_days) return event.recurrence_days.split(',').includes(todayName)
          if (event.recurrence_day) return todayName === event.recurrence_day
          if (event.recurrence === 'monthly_last_friday') {
            if (activeDate.getDay() !== 5) return false
            const nw = new Date(activeDate); nw.setDate(activeDate.getDate()+7)
            return nw.getMonth() !== activeDate.getMonth()
          }
        }
        const cats = getCategories(event).split(' ')
        if (activeCategory !== 'all' && !cats.includes(activeCategory)) return false
        if (activeSearch) {
          const searchText = ((event.title||'')+' '+(event.description||'')+' '+(event.location||'')).toLowerCase()
          if (!searchText.includes(activeSearch.toLowerCase())) return false
        }
        // Supplemental (cross-city) events only appear when radius is widened
        if ((event as any)._supplemental && !(radiusActive && radiusMiles >= 20)) return false
        if (radiusActive && userLat && userLng && event.lat && event.lng) {
          if (distanceMilesFromUser(userLat, userLng, event.lat, event.lng) > radiusMiles) return false
        }
        return true
      })

      visible.sort((a,b) => { const af = isFeaturedEvent(a)?0:1, bf = isFeaturedEvent(b)?0:1; if (af!==bf) return af-bf; return (a.title||'').localeCompare(b.title||'') })

      const featuredEvents = visible.filter(e => isFeaturedEvent(e))
      const regularEvents = visible.filter(e => !isFeaturedEvent(e))
      let bandEvents = [...featuredEvents]
      if (dailyFeaturedTitle) {
        const dailyEvent = allEvents.find(e => e.title === dailyFeaturedTitle)
        if (dailyEvent && !bandEvents.find(e => e.title === dailyFeaturedTitle)) bandEvents.unshift(dailyEvent)
      }

      const band = document.getElementById('featured-band')
      const bandCards = document.getElementById('featured-band-cards')
      if (band && bandCards && bandEvents.length > 0 && currentView === 'list') {
        band.style.display = 'block'
        const MS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
        bandCards.innerHTML = bandEvents.map(e => {
          const d = e.date ? new Date(e.date+'T12:00:00') : null
          const month = d ? MS[d.getMonth()] : 'See'
          const day = d ? d.getDate() : '—'
          const cats = getCategories(e).split(' ').filter(Boolean)
          const tagMap: Record<string,string> = {music:'t-music',outdoor:'t-outdoor',food:'t-food',arts:'t-arts',sports:'t-sports',family:'t-family',wellness:'t-community',community:'t-community',free:'t-free',paid:'t-paid'}
          const labels: Record<string,string> = {music:'Music',outdoor:'Outdoor',food:'Food & Drink',arts:'Arts',sports:'Sports',family:'Family',wellness:'Wellness',community:'Community',free:'Free',paid:'Paid'}
          const tagHTML = cats.slice(0,3).map((c:string) => `<span class="cal-tag ${tagMap[c]||''}">${labels[c]||c}</span>`).join('')
          const src = (e.source||'').replace('The Park Record','Park Record').replace('Visit Park City','visitparkcity.com').replace('Google Events','Google')
          return `<div class="featured-band-card" onclick="openEventModal(this)" data-title="${(e.title||'').replace(/"/g,'&quot;')}" data-date="${e.date||''}" data-end-date="${e.end_date||''}" data-location="${(e.location||'').replace(/"/g,'&quot;')}" data-link="${e.link||''}" data-description="${(e.description||'').replace(/"/g,'&quot;').replace(/\n/g,' ')}" data-source="${(e.source||'').replace(/"/g,'&quot;')}" data-categories="${cats.join(' ')}" data-start-time="${e.start_time||''}" data-end-time="${e.end_time||''}" style="cursor:pointer"><div class="fbc-time"><div class="h">${month}</div><div class="ap">${day}</div>${e.start_time?`<div style="font-size:9px;color:white;margin-top:3px;white-space:nowrap">${e.start_time}${e.end_time?"–"+e.end_time:""}</div>`:''}</div><div class="fbc-info"><h4>${e.title}</h4><p>${(e.description||'').slice(0,100)||(e.location?'📍 '+e.location:'')}</p><div class="cal-tags" style="margin-top:6px">${tagHTML}<span class="cal-source">via ${src}</span></div></div></div>`
        }).join('')
      } else if (band) {
        band.style.display = 'none'
      }

      const regularLabel = bandEvents.length > 0 && currentView === 'list' && regularEvents.length > 0 ? `<div class="regular-events-label">All events</div>` : ''
      if (container) container.innerHTML = regularLabel + regularEvents.map(event => renderEvent(event, selDateStr)).join('')
      if (noResults) noResults.style.display = (visible.length === 0 && currentView === 'list') ? 'block' : 'none'

      if (!activeSearch && dateLabel) {
        if (showAllDates) dateLabel.textContent = `${CITIES[currentCity]?.label || 'Local'} — all upcoming events`
        else dateLabel.textContent = `${DAYS[activeDate.getDay()]}, ${MONTHS_FULL[activeDate.getMonth()]} ${activeDate.getDate()} — ${CITIES[currentCity]?.name || 'Local'}`
      }

      if (currentView === 'map' && map) updateMapMarkers()
    }

    function applyDateFilter(dateObj: Date) {
      activeDate = dateObj
      showAllDates = false
      applyFilters()
      const btn = document.getElementById('cal-today-btn') as HTMLButtonElement
      if (btn) btn.style.display = (dateObj.toDateString() !== today.toDateString() || weekOffset !== 0) ? 'inline-block' : 'none'
    }

    function applySearch(q: string) {
      activeSearch = q
      if (searchClear) searchClear.style.display = q ? 'block' : 'none'
      showAllDates = !!q
      applyFilters()
    }

    function countEventsOnDate(dateObj: Date): number {
      if (!allEvents.length) return 0
      const sel = dateToStr(dateObj)
      const dayNames = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday']
      const todayName = dayNames[dateObj.getDay()]
      return allEvents.filter(event => {
        if ((event as any)._supplemental && !(radiusActive && radiusMiles >= 20)) return false
        const s = parseDate(event.date)
        const en = event.end_date ? parseDate(event.end_date) : s
        if (!s) return false
        if (sel < s || sel > (en || s)) return false
        if (event.recurrence_days) return event.recurrence_days.split(',').includes(todayName)
        if (event.recurrence_day) return todayName === event.recurrence_day
        if (event.recurrence === 'monthly_last_friday') {
          if (dateObj.getDay() !== 5) return false
          const nw = new Date(dateObj); nw.setDate(dateObj.getDate()+7)
          return nw.getMonth() !== dateObj.getMonth()
        }
        return true
      }).length
    }

    function buildDayChips() {
      if (!dayContainer) return
      dayContainer.innerHTML = ''
      for (let i = 0; i <= 6; i++) {
        const d = new Date(today)
        d.setDate(today.getDate() + (weekOffset * 7) + i)
        const div = document.createElement('div')
        const isSelected = d.toDateString() === selectedDate.toDateString()
        div.className = 'cal-day' + (isSelected ? ' active' : '')
        const count = countEventsOnDate(d)
        div.innerHTML = `<span class="d">${DAYS[d.getDay()]}</span><span class="n">${d.getDate()}</span><span class="day-count" ${count===0?'style="visibility:hidden"':''}>${count}</span>`
        const captured = new Date(d)
        div.addEventListener('click', () => {
          selectedDate = new Date(captured)
          document.querySelectorAll('.cal-day').forEach(x => x.classList.remove('active'))
          div.classList.add('active')
          document.querySelectorAll('.cal-filter').forEach(x => x.classList.remove('active'))
          document.querySelector('.cal-filter[data-filter="all"]')?.classList.add('active')
          activeCategory = 'all'
          if (searchInput) { searchInput.value = ''; activeSearch = '' }
          if (searchClear) searchClear.style.display = 'none'
          applyDateFilter(captured)
        })
        dayContainer.appendChild(div)
      }
      const label = document.getElementById('cal-days-label')
      if (label) {
        if (weekOffset === 0) label.textContent = 'This week'
        else if (weekOffset === 1) label.textContent = 'Next week'
        else if (weekOffset === -1) label.textContent = 'Last week'
        else { const s = new Date(today); s.setDate(today.getDate()+weekOffset*7); label.textContent = `${MONTHS_FULL[s.getMonth()]} ${s.getDate()}+` }
      }
    }

    function buildMonthPicker() {
      const title = document.getElementById('cal-month-title')
      const daysEl = document.getElementById('cal-month-days')
      if (!title || !daysEl) return
      const yr = pickerDate.getFullYear(), mo = pickerDate.getMonth()
      title.textContent = `${MONTHS_FULL[mo]} ${yr}`
      const firstDay = new Date(yr, mo, 1).getDay()
      const daysInMonth = new Date(yr, mo+1, 0).getDate()
      const eventDates = new Set<number>()
      document.querySelectorAll('.cal-event').forEach((card: any) => {
        const s = card.dataset.start
        if (s) { const [sy,sm,sd] = s.split('-').map(Number); if (sy===yr && sm-1===mo) eventDates.add(sd) }
      })
      daysEl.innerHTML = ''
      for (let i = 0; i < firstDay; i++) { const e = document.createElement('div'); e.className = 'cal-month-day empty'; daysEl.appendChild(e) }
      for (let d = 1; d <= daysInMonth; d++) {
        const dayEl = document.createElement('div')
        const thisDate = new Date(yr, mo, d)
        const isToday = thisDate.toDateString() === today.toDateString()
        const isSelected = thisDate.toDateString() === selectedDate.toDateString()
        const isPast = thisDate < new Date(today.getFullYear(), today.getMonth(), today.getDate())
        dayEl.className = 'cal-month-day' + (isToday?' today':'') + (isSelected?' selected':'') + (isPast&&!isToday?' past':'') + (eventDates.has(d)?' has-events':'')
        dayEl.textContent = String(d)
        dayEl.addEventListener('click', () => {
          selectedDate = new Date(yr, mo, d)
          document.querySelectorAll('.cal-month-day').forEach(x => x.classList.remove('selected'))
          dayEl.classList.add('selected')
          const picker = document.getElementById('cal-month-picker')
          if (picker) picker.style.display = 'none'
          const toggle = document.getElementById('cal-month-toggle')
          if (toggle) toggle.classList.remove('active')
          document.querySelectorAll('.cal-filter').forEach(x => x.classList.remove('active'))
          document.querySelector('.cal-filter[data-filter="all"]')?.classList.add('active')
          if (searchInput) { searchInput.value = ''; activeSearch = '' }
          if (searchClear) searchClear.style.display = 'none'
          applyDateFilter(selectedDate)
        })
        daysEl.appendChild(dayEl)
      }
    }

    function initMap() {
      const L = window.L
      if (!L) return
      const cityConfig = CITY_CENTERS[currentCity] || CITY_CENTERS.parkcity
      if (map) { map.setView(cityConfig.center, cityConfig.zoom); return }
      map = L.map('cal-map').setView(cityConfig.center, cityConfig.zoom)
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '© OpenStreetMap contributors' }).addTo(map)
    }

    function updateMapMarkers() {
      if (!map || !window.L) return
      mapMarkers.forEach(m => m.remove()); mapMarkers = []
      const bounds: [number,number][] = []
      document.querySelectorAll('.cal-event').forEach((card: any) => {
        if (card.style.display === 'none') return
        const lat = parseFloat(card.dataset.lat), lng = parseFloat(card.dataset.lng)
        if (!lat || !lng || isNaN(lat) || isNaN(lng)) return
        const marker = window.L.circleMarker([lat, lng], { radius:9, fillColor:'#534AB7', color:'white', weight:2, opacity:1, fillOpacity:0.9 })
        marker.bindPopup(`<div class="map-popup"><h4>${card.dataset.title||''}</h4>${card.dataset.location?`<p>📍 ${card.dataset.location}</p>`:''}<a href="${card.dataset.link||'#'}" target="_blank">View event →</a></div>`)
        marker.addTo(map); mapMarkers.push(marker); bounds.push([lat, lng])
      })
      if (bounds.length > 0) { try { map.fitBounds(bounds, { padding:[40,40], maxZoom:14 }) } catch(e) {} }
    }

    function setView(view: string) {
      currentView = view
      const listContainer = document.getElementById('cal-events-container')
      const mapContainer = document.getElementById('cal-map-container')
      const noResultsEl = document.getElementById('no-results')
      const btnList = document.getElementById('btn-list'), btnMap = document.getElementById('btn-map')
      const featBand = document.getElementById('featured-band')
      if (view === 'map') {
        if (listContainer) listContainer.style.display = 'none'
        if (noResultsEl) noResultsEl.style.display = 'none'
        if (mapContainer) mapContainer.style.display = 'block'
        if (featBand) featBand.style.display = 'none'
        if (btnList) btnList.classList.remove('active')
        if (btnMap) btnMap.classList.add('active')
        initMap()
        setTimeout(() => { if (map) { map.invalidateSize(); updateMapMarkers() } }, 100)
      } else {
        if (listContainer) listContainer.style.display = 'grid'
        if (mapContainer) mapContainer.style.display = 'none'
        if (btnList) btnList.classList.add('active')
        if (btnMap) btnMap.classList.remove('active')
        applyFilters()
      }
    }

    function updateNavLinks(cityKey: string) {
      const about = document.getElementById('nav-about') as HTMLAnchorElement
      const weekend = document.getElementById('nav-weekend') as HTMLAnchorElement
      const venues = document.getElementById('nav-venues') as HTMLAnchorElement
      const city = CITIES[cityKey]
      if (city) {
        if (about) { about.href = city.aboutPage||'/about'; about.textContent = city.aboutLabel||'About' }
        if (weekend) { weekend.href = `/this-weekend?city=${cityKey}`; weekend.style.display = '' }
        if (venues) { venues.href = `/venues?city=${cityKey}`; venues.style.display = '' }
      }
    }

    function loadCity(cityKey: string) {
      const city = CITIES[cityKey]
      if (!city) return
      currentCity = cityKey
      const calLoc = document.getElementById('cal-loc-label')
      if (calLoc) calLoc.innerHTML = `📍 ${city.name} &nbsp;▾`
      if (container) container.innerHTML = '<div style="padding:32px;text-align:center;color:rgba(255,255,255,0.4);font-size:14px;">Loading events...</div>'
      const mainFetch = fetch('/'+city.file).then((r: Response) => r.json())
      const suppFetch = city.supplementalFile ? fetch('/'+city.supplementalFile).then((r: Response) => r.json()).catch(() => ({events:[]})) : Promise.resolve({events:[]})
      Promise.all([mainFetch, suppFetch]).then(([data, suppData]: any) => {
        const _suppMarked = (suppData.events || []).map((e: any) => ({ ...e, _supplemental: true }))
        allEvents = [...(data.events || []), ..._suppMarked]
        allEvents = allEvents.filter((e: any) => !city.junk.some((j: string) => e.title.toLowerCase().includes(j)))
        const dedupMap = new Map<string,any>()
        allEvents.forEach((e: any) => {
          const key = `${(e.title||'').toLowerCase().replace(/^[("'\-\s]+/,'').substring(0,35)}|${(e.date||'').substring(0,10)}`
          const existing = dedupMap.get(key)
          if (!existing) { dedupMap.set(key, e) } else {
            const eS = (e.source==='The Park Record'?2:0)+(e.start_time?1:0)
            const exS = (existing.source==='The Park Record'?2:0)+(existing.start_time?1:0)
            if (eS > exS) dedupMap.set(key, e)
          }
        })
        allEvents = Array.from(dedupMap.values())
        dailyFeaturedTitle = getDailyFeaturedTitle()
        const heroStat = document.querySelector('.hero-stat .num') as HTMLElement
        if (heroStat) {
          const today = new Date()
          today.setHours(0, 0, 0, 0)
          const weekEnd = new Date(today)
          weekEnd.setDate(weekEnd.getDate() + 7)
          const weekCount = allEvents.filter((e: any) => {
            if (e._supplemental) return false
            const d = (e.date || '').slice(0, 10)
            if (!/^\d{4}-\d{2}-\d{2}$/.test(d)) return false
            const evDate = new Date(d + 'T00:00:00')
            return evDate >= today && evDate < weekEnd
          }).length
          heroStat.textContent = weekCount.toLocaleString()
        }
        if (data.updated_at) {
          const hrs = Math.round((new Date().getTime() - new Date(data.updated_at).getTime()) / 3600000)
          if (dateLabel) dateLabel.textContent = `${city.label} — updated ${hrs < 1 ? 'just now' : hrs + ' hours ago'}`
        }
        activeDate = today; selectedDate = new Date(today); weekOffset = 0; showAllDates = false
        buildDayChips(); dailyFeaturedTitle = getDailyFeaturedTitle(today); applyFilters()
        const params = new URLSearchParams(window.location.search)
        const evTitle = params.get('event'), evDate = params.get('date')
        if (evTitle) {
          const match = allEvents.find((e: any) => e.title === evTitle && (!evDate || e.date?.slice(0,10) === evDate)) || allEvents.find((e: any) => e.title === evTitle)
          if (match) {
            if (match.date) { const d = new Date(match.date+'T12:00:00'); activeDate = d; selectedDate = new Date(d); buildDayChips(); applyFilters() }
            setTimeout(() => {
              const cards = document.querySelectorAll('.cal-event,.featured-band-card')
              for (const card of Array.from(cards)) { if ((card as any).dataset.title === evTitle) { openEventModal(card as HTMLElement); card.scrollIntoView({behavior:'smooth',block:'center'}); break } }
            }, 600)
          }
        }
      }).catch(() => {
        if (container) container.innerHTML = `<div style="padding:32px;text-align:center;color:rgba(255,255,255,0.4);font-size:14px;">Events coming soon for ${city.name}!</div>`
      })
    }

    function switchCity(cityKey: string, el: HTMLElement | null) {
      document.querySelectorAll('.loc-chip').forEach(c => c.classList.remove('active'))
      if (el) el.classList.add('active')
      activeCategory = 'all'; activeSearch = ''; weekOffset = 0
      if (searchInput) { searchInput.value = '' }
      if (searchClear) searchClear.style.display = 'none'
      document.querySelectorAll('.cal-filter').forEach(x => x.classList.remove('active'))
      document.querySelector('.cal-filter[data-filter="all"]')?.classList.add('active')
      buildDayChips(); loadCity(cityKey); updateNavLinks(cityKey)
      document.getElementById('events')?.scrollIntoView({ behavior: 'smooth' })
      return false
    }

    function openEventModal(card: HTMLElement) {
      modalCardRef = card
      const title = card.dataset.title||'', desc = card.dataset.description||'', date = card.dataset.date||''
      const endDate = card.dataset.endDate||'', location = card.dataset.location||'', link = card.dataset.link||'#'
      const venueName = card.dataset.venueName||''
      const address = card.dataset.address||''
      const source = card.dataset.source||''
      const cats = (card.dataset.categories||'').split(' ').filter(Boolean)
      const tagMap: Record<string,[string,string]> = { music:['t-music','Music'], outdoor:['t-outdoor','Outdoor'], food:['t-food','Food & Drink'], arts:['t-arts','Arts'], sports:['t-sports','Sports'], family:['t-family','Family'], wellness:['t-community','Wellness'], community:['t-community','Community'], free:['t-free','Free'], paid:['t-paid','Paid'] }
      const tagsHTML = cats.slice(0,4).map(c => { const t = tagMap[c]; return t ? `<span class="cal-tag ${t[0]}">${t[1]}</span>` : '' }).join('')
      const mTitle = document.getElementById('modal-title'), mDesc = document.getElementById('modal-desc')
      const mTags = document.getElementById('modal-tags'), mLink = document.getElementById('modal-link') as HTMLAnchorElement
      const mMeta = document.getElementById('modal-meta')
      if (mTitle) mTitle.textContent = title
      if (mDesc) mDesc.textContent = desc || 'See the event website for full details.'
      if (mTags) mTags.innerHTML = tagsHTML
      if (mLink) { mLink.href = link; mLink.style.display = link&&link!=='#'?'':'none' }
      const MF = ['January','February','March','April','May','June','July','August','September','October','November','December']
      const DF = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday']
      let dateStr = ''
      if (date) {
        const d = new Date(date+'T12:00:00')
        dateStr = `${DF[d.getDay()]}, ${MF[d.getMonth()]} ${d.getDate()}, ${d.getFullYear()}`
        if (endDate && endDate !== date) { const ed = new Date(endDate+'T12:00:00'); dateStr += ` – ${DF[ed.getDay()]}, ${MF[ed.getMonth()]} ${ed.getDate()}, ${ed.getFullYear()}` }
      }
      const meta: string[] = []
      if (dateStr) meta.push(`<div style="display:flex;align-items:center;gap:10px;font-size:14px;color:rgba(255,255,255,0.7)"><span style="font-size:16px">📅</span>${dateStr}</div>`)
      const startTime = card.dataset.startTime||'', endTime = card.dataset.endTime||''
      if (startTime) meta.push(`<div style="display:flex;align-items:center;gap:10px;font-size:14px;color:rgba(255,255,255,0.7)"><span style="font-size:16px">🕐</span>${endTime?startTime+' – '+endTime:startTime}</div>`)
      // Prefer structured venue_name + address when available (cleaner display)
      if (venueName) {
        meta.push(`<div style="display:flex;align-items:center;gap:10px;font-size:14px;color:rgba(255,255,255,0.7)"><span style="font-size:16px">📍</span>${venueName}</div>`)
        if (address) {
          meta.push(`<div style="display:flex;align-items:center;gap:10px;font-size:13px;color:rgba(255,255,255,0.55);margin-left:26px">${address}</div>`)
        }
      } else if (location) {
        meta.push(`<div style="display:flex;align-items:center;gap:10px;font-size:14px;color:rgba(255,255,255,0.7)"><span style="font-size:16px">📍</span>${location}</div>`)
      }
      if (source) meta.push(`<div style="display:flex;align-items:center;gap:10px;font-size:14px;color:rgba(255,255,255,0.4)"><span style="font-size:16px">🔗</span>via ${source}</div>`)
      if (mMeta) mMeta.innerHTML = meta.join('')
      const overlay = document.getElementById('event-modal-overlay'), modal = document.getElementById('event-modal')
      if (overlay) overlay.style.display = 'block'
      if (modal) modal.style.display = 'block'
      document.body.style.overflow = 'hidden'
    }

    function closeEventModal() {
      const overlay = document.getElementById('event-modal-overlay'), modal = document.getElementById('event-modal')
      if (overlay) overlay.style.display = 'none'
      if (modal) modal.style.display = 'none'
      document.body.style.overflow = ''
      modalCardRef = null
    }

    function makeICSContent(title: string, dateStr: string, startTime: string, endTime: string, location: string, description: string): string {
      const safe = (s: string) => (s||'').replace(/,/g,'\\,').replace(/\n/g,'\\n')
      const now = new Date().toISOString().replace(/[-:]/g,'').slice(0,15)+'Z'
      function toICSTime(date: string, time: string) {
        if (!date) return null
        const d = date.replace(/-/g,'')
        if (!time) return null
        const m = time.match(/(\d{1,2}):(\d{2})\s?(AM|PM)/i)
        if (!m) return null
        let h = parseInt(m[1]); const mn = m[2]; const ap = m[3].toUpperCase()
        if (ap==='PM'&&h!==12) h+=12; if (ap==='AM'&&h===12) h=0
        return `${d}T${String(h).padStart(2,'0')}${mn}00`
      }
      // If start_time is present but end_time is missing, default to start + 1 hour
      // so the entry isn't a zero-duration blip in the user's calendar.
      function toICSTimePlusHour(date: string, time: string) {
        if (!date || !time) return null
        const d = date.replace(/-/g,'')
        const m = time.match(/(\d{1,2}):(\d{2})\s?(AM|PM)/i)
        if (!m) return null
        let h = parseInt(m[1]); const mn = m[2]; const ap = m[3].toUpperCase()
        if (ap==='PM'&&h!==12) h+=12; if (ap==='AM'&&h===12) h=0
        h = (h + 1) % 24
        return `${d}T${String(h).padStart(2,'0')}${mn}00`
      }
      const dtStart = toICSTime(dateStr, startTime)
      const dtEnd = endTime
        ? toICSTime(dateStr, endTime)
        : (startTime ? toICSTimePlusHour(dateStr, startTime) : null)
      const startLine = dtStart ? `DTSTART:${dtStart}` : `DTSTART;VALUE=DATE:${dateStr.replace(/-/g,'')}`
      const endLine = dtEnd ? `DTEND:${dtEnd}` : `DTEND;VALUE=DATE:${dateStr.replace(/-/g,'')}`
      return ['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//Yoocal//EN','BEGIN:VEVENT',startLine,endLine,`DTSTAMP:${now}`,`SUMMARY:${safe(title)}`,`LOCATION:${safe(location)}`,`DESCRIPTION:${safe(description)}`,'END:VEVENT','END:VCALENDAR'].join('\r\n')
    }

    function openAtcDropdown(e: Event, btn: HTMLElement) {
      e.preventDefault(); e.stopPropagation()
      const card = (btn&&btn.id==='modal-atc') ? modalCardRef : (btn?btn.closest('.cal-event') as HTMLElement:null)
      if (!card) return
      const title = (card as any).dataset.title||'', dateStr = (card as any).dataset.start||(card as any).dataset.date||''
      const location = (card as any).dataset.location||'', startTime = (card as any).dataset.startTime||'', endTime = (card as any).dataset.endTime||''
      const rawLink = (card as any).dataset.link||''
      const description = rawLink ? `More info: ${rawLink}` : ''
      function toCalTime(date: string, time: string) {
        if (!date) return ''
        if (!time) return date.replace(/-/g,'')
        const m = time.match(/(\d{1,2}):(\d{2})\s?(AM|PM)/i)
        if (!m) return date.replace(/-/g,'')
        let h = parseInt(m[1]); const mn = m[2]; const ap = m[3].toUpperCase()
        if (ap==='PM'&&h!==12) h+=12; if (ap==='AM'&&h===12) h=0
        return `${date.replace(/-/g,'')}T${String(h).padStart(2,'0')}${mn}00`
      }
      // If we have start_time but no end_time, default to start + 1 hour so the
      // calendar entry isn't a zero-duration blip. If no start_time at all, it's
      // an all-day event (date-only formatting).
      function addHourToCalTime(date: string, time: string): string {
        if (!date || !time) return date.replace(/-/g,'')
        const m = time.match(/(\d{1,2}):(\d{2})\s?(AM|PM)/i)
        if (!m) return date.replace(/-/g,'')
        let h = parseInt(m[1]); const mn = m[2]; const ap = m[3].toUpperCase()
        if (ap==='PM'&&h!==12) h+=12; if (ap==='AM'&&h===12) h=0
        h = (h + 1) % 24  // wrap to 0 if event starts at 11 PM
        return `${date.replace(/-/g,'')}T${String(h).padStart(2,'0')}${mn}00`
      }
      const gStart = toCalTime(dateStr, startTime)
      const gEnd = startTime
        ? (endTime ? toCalTime(dateStr, endTime) : addHourToCalTime(dateStr, startTime))
        : dateStr.replace(/-/g,'')
      const googleLink = document.getElementById('atc-google') as HTMLAnchorElement
      if (googleLink) googleLink.href = `https://calendar.google.com/calendar/render?action=TEMPLATE&text=${encodeURIComponent(title)}&dates=${gStart}/${gEnd}&location=${encodeURIComponent(location)}&details=${encodeURIComponent(description)}`
      const ics = makeICSContent(title, dateStr, startTime, endTime, location, description)
      const blob = new Blob([ics], {type:'text/calendar'})
      const icsUrl = URL.createObjectURL(blob)
      const filename = `${title.slice(0,40).replace(/\s+/g,'-')}.ics`
      const appleLink = document.getElementById('atc-apple') as HTMLAnchorElement
      if (appleLink) { appleLink.href = icsUrl; appleLink.download = filename }
      const outlookLink = document.getElementById('atc-outlook') as HTMLAnchorElement
      if (outlookLink) { outlookLink.href = icsUrl; outlookLink.download = filename }
      const dd = document.getElementById('atc-dropdown')
      const anchorBtn = (btn&&btn.id==='modal-atc') ? document.getElementById('modal-atc') : btn
      if (dd && anchorBtn) {
        const rect = anchorBtn.getBoundingClientRect()
        let left = rect.left
        if (left+190 > window.innerWidth) left = window.innerWidth-196
        dd.style.top = (rect.bottom+6)+'px'; dd.style.left = left+'px'
        dd.classList.add('open')
      }
    }

    function openAtcFromModal() { if (modalCardRef) { const btn = document.getElementById('modal-atc') as HTMLElement; openAtcDropdown(new MouseEvent('click'), btn) } }

    function openShareMenu(e: Event) {
      e.stopPropagation()
      if (!modalCardRef) return
      const title = (modalCardRef as any).dataset.title||'', date = (modalCardRef as any).dataset.date||''
      const yoocalUrl = `https://www.yoocal.com/?city=${currentCity}&event=${encodeURIComponent(title)}&date=${date}`
      const shareText = `Check out "${title}"${date?' on '+date:''} — via Yoocal`
      const nativeBtn = document.getElementById('share-native') as HTMLAnchorElement
      if (navigator.share) { nativeBtn.style.display='flex'; nativeBtn.onclick = (ev) => { ev.preventDefault(); closeShareMenu(); navigator.share({title, text:shareText, url:yoocalUrl}) } } else { nativeBtn.style.display='none' }
      ;(document.getElementById('share-sms') as HTMLAnchorElement).href = `sms:?body=${encodeURIComponent(shareText+' '+yoocalUrl)}`
      ;(document.getElementById('share-email') as HTMLAnchorElement).href = `mailto:?subject=${encodeURIComponent(title)}&body=${encodeURIComponent(shareText+'\n\n'+yoocalUrl)}`
      ;(document.getElementById('share-x') as HTMLAnchorElement).href = `https://x.com/intent/tweet?text=${encodeURIComponent(shareText)}&url=${encodeURIComponent(yoocalUrl)}`
      ;(document.getElementById('share-facebook') as HTMLAnchorElement).href = `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(yoocalUrl)}`
      const dd = document.getElementById('share-dropdown'), btn = document.getElementById('modal-share')
      if (dd && btn) { const rect = btn.getBoundingClientRect(); let left = rect.left; if (left+210>window.innerWidth) left=window.innerWidth-216; dd.style.top=(rect.bottom+6)+'px'; dd.style.left=left+'px'; dd.style.display='block' }
    }

    function closeShareMenu() { const dd = document.getElementById('share-dropdown'); if (dd) dd.style.display='none' }

    function copyShareLink(e: Event) {
      e.preventDefault(); closeShareMenu()
      const title = (modalCardRef as any)?.dataset.title||'', date = (modalCardRef as any)?.dataset.date||''
      const yoocalUrl = `https://www.yoocal.com/?city=${currentCity}&event=${encodeURIComponent(title)}&date=${date}`
      navigator.clipboard.writeText(yoocalUrl).then(() => {
        const btn = document.getElementById('modal-share')
        if (btn) { const orig = btn.innerHTML; btn.innerHTML='✓ Copied!'; setTimeout(()=>{ btn.innerHTML=orig },2000) }
      })
    }

    function useMyLocation() {
      const btn = document.getElementById('radius-locate-btn') as HTMLButtonElement
      const status = document.getElementById('radius-status') as HTMLElement
      if (btn) btn.innerHTML = '⏳ Locating...'
      navigator.geolocation.getCurrentPosition(pos => {
        userLat = pos.coords.latitude; userLng = pos.coords.longitude; window.userLat = userLat
        radiusActive = true
        if (btn) { btn.innerHTML='✅ Location set'; btn.style.background='var(--purple)'; btn.style.borderColor='var(--purple)' }
        const sliderWrap = document.getElementById('radius-slider-wrap')
        if (sliderWrap) sliderWrap.style.display='flex'
        if (status) status.textContent=`Showing events within ${radiusMiles} miles`
        applyFilters()
      }, () => {
        if (btn) btn.innerHTML='📍 Use my location'
        if (status) status.textContent='Location unavailable — try a zip code'
      }, { timeout:8000 })
    }

    function onRadiusChange(val: string) {
      radiusMiles = parseInt(val)
      const lbl = document.getElementById('radius-label'), status = document.getElementById('radius-status')
      if (lbl) lbl.textContent=`${val} mi`
      if (status) status.textContent=`Showing events within ${val} miles`
      buildDayChips()
      applyFilters()
    }

    function clearRadius() {
      userLat=null; userLng=null; window.userLat=null; radiusActive=false
      const sliderWrap = document.getElementById('radius-slider-wrap'), status = document.getElementById('radius-status')
      const zipInput = document.getElementById('radius-zip') as HTMLInputElement
      const locBtn = document.getElementById('radius-locate-btn') as HTMLButtonElement
      if (sliderWrap) sliderWrap.style.display='none'
      if (status) status.textContent=''
      if (zipInput) zipInput.value=''
      if (locBtn) { locBtn.innerHTML='📍 Use my location'; locBtn.style.background='rgba(255,255,255,0.07)'; locBtn.style.borderColor='rgba(255,255,255,0.15)' }
      applyFilters()
    }

    function jumpToToday() {
      weekOffset=0; selectedDate=new Date()
      buildDayChips(); applyDateFilter(selectedDate)
      const btn = document.getElementById('cal-today-btn') as HTMLButtonElement
      if (btn) btn.style.display='none'
      const lbl = document.getElementById('cal-days-label')
      if (lbl) lbl.textContent='This week'
      document.querySelectorAll('.cal-filter').forEach(x=>x.classList.remove('active'))
      document.querySelector('.cal-filter[data-filter="all"]')?.classList.add('active')
    }

    function setConfirmedLocation(cityName: string, lat: number, lng: number) {
      userLat=lat; userLng=lng; window.userLat=lat
      try { localStorage.setItem('yoocal_lat',String(lat)); localStorage.setItem('yoocal_lng',String(lng)); localStorage.setItem('yoocal_city',cityName) } catch(e) {}
      const nameEl = document.getElementById('confirmed-city-name'), radiusLbl = document.getElementById('confirmed-radius-label')
      const confirmed = document.getElementById('location-confirmed-band'), chips = document.getElementById('location-city-chips')
      if (nameEl) nameEl.textContent=cityName
      if (confirmed) confirmed.style.display='flex'
      if (chips) chips.style.display='none'
      radiusActive=true
      const sliderWrap = document.getElementById('radius-slider-wrap')
      if (sliderWrap) sliderWrap.style.display='flex'
      const radiusVal = (document.getElementById('radius-slider') as HTMLInputElement)?.value || '25'
      if (radiusLbl) radiusLbl.textContent=`Showing events within ${radiusVal} miles`
      const status = document.getElementById('radius-status')
      if (status) status.textContent=`Showing events within ${radiusVal} mi of ${cityName}`
      applyFilters()
      document.getElementById('events')?.scrollIntoView({behavior:'smooth'})
    }

    function heroUseMyLocation() {
      const btn = document.getElementById('hero-locate-btn') as HTMLButtonElement
      if (btn) { btn.textContent='Locating…'; btn.disabled=true }
      if (!navigator.geolocation) { if (btn) { btn.textContent='📍 Use my location'; btn.disabled=false }; alert('Geolocation not supported'); return }
      navigator.geolocation.getCurrentPosition(pos => {
        const lat=pos.coords.latitude, lng=pos.coords.longitude
        const apiKey = process.env.NEXT_PUBLIC_GOOGLE_MAPS_KEY
        if (apiKey) {
          fetch(`https://maps.googleapis.com/maps/api/geocode/json?latlng=${lat},${lng}&key=${apiKey}`).then(r=>r.json()).then(data=>{
            let city='Your location'
            if (data.results?.length) { const comps=data.results[0].address_components; const locality=comps.find((c:any)=>c.types.includes('locality')); const state=comps.find((c:any)=>c.types.includes('administrative_area_level_1')); if (locality&&state) city=`${locality.long_name}, ${state.short_name}`; else if (locality) city=locality.long_name }
            if (btn) { btn.textContent='📍 Use my location'; btn.disabled=false }
            setConfirmedLocation(city, lat, lng)
          }).catch(()=>{ if (btn){btn.textContent='📍 Use my location';btn.disabled=false}; setConfirmedLocation('Your location',lat,lng) })
        } else { if (btn){btn.textContent='📍 Use my location';btn.disabled=false}; setConfirmedLocation('Your location',lat,lng) }
      }, ()=>{ if (btn){btn.textContent='📍 Use my location';btn.disabled=false}; alert('Could not get location. Try searching by city below.') })
    }

    function clearHeroLocation() {
      userLat=null; userLng=null; window.userLat=null; radiusActive=false
      try { localStorage.removeItem('yoocal_lat'); localStorage.removeItem('yoocal_lng'); localStorage.removeItem('yoocal_city') } catch(e) {}
      const confirmed=document.getElementById('location-confirmed-band'), chips=document.getElementById('location-city-chips')
      const heroInput=document.getElementById('hero-location-input') as HTMLInputElement
      const sliderWrap=document.getElementById('radius-slider-wrap'), status=document.getElementById('radius-status')
      if (confirmed) confirmed.style.display='none'
      if (chips) chips.style.display='flex'
      if (heroInput) heroInput.value=''
      if (sliderWrap) sliderWrap.style.display='none'
      if (status) status.textContent=''
      applyFilters()
    }

    function initPlacesAutocomplete() {
      if (!window.google) return
      const inputs = [document.getElementById('hero-location-input'), document.getElementById('radius-zip')]
      inputs.forEach(input => {
        if (!input) return
        const ac = new window.google.maps.places.Autocomplete(input as HTMLInputElement, { types:['(regions)'], componentRestrictions:{country:'us'}, fields:['geometry','formatted_address','address_components'] })
        ac.addListener('place_changed', () => {
          const place = ac.getPlace()
          if (!place.geometry) return
          const lat=place.geometry.location.lat(), lng=place.geometry.location.lng()
          const comps=place.address_components||[]
          const locality=comps.find((c:any)=>c.types.includes('locality')), state=comps.find((c:any)=>c.types.includes('administrative_area_level_1'))
          let cityName = locality ? locality.long_name : (place.formatted_address||(input as HTMLInputElement).value)
          if (locality&&state) cityName=`${locality.long_name}, ${state.short_name}`
          setConfirmedLocation(cityName, lat, lng)
        })
      })
    }

    function toggleEyebrowDropdown(e: Event) {
      e.stopPropagation()
      const dd=document.getElementById('hero-eyebrow-dropdown'), trigger=e.currentTarget as HTMLElement
      if (!dd||!trigger) return
      const rect=trigger.getBoundingClientRect(), ddWidth=220
      let left=rect.left+rect.width/2-ddWidth/2
      left=Math.max(12, Math.min(left, window.innerWidth-ddWidth-12))
      dd.style.top=(rect.bottom+8)+'px'; dd.style.left=left+'px'
      dd.classList.toggle('open')
    }

    function eyebrowSwitchCity(e: Event, cityKey: string) {
      e.stopPropagation()
      document.getElementById('hero-eyebrow-dropdown')?.classList.remove('open')
      const chip = document.querySelector(`.loc-chip[data-city="${cityKey}"]`) as HTMLElement
      switchCity(cityKey, chip)
    }

    // Expose all functions to window for inline handlers
    window.setView = setView
    window.switchCity = switchCity
    window.useMyLocation = useMyLocation
    window.heroUseMyLocation = heroUseMyLocation
    window.clearHeroLocation = clearHeroLocation
    window.jumpToToday = jumpToToday
    window.onRadiusChange = onRadiusChange
    window.clearRadius = clearRadius
    window.openEventModal = openEventModal
    window.closeEventModal = closeEventModal
    window.openAtcDropdown = openAtcDropdown
    window.openAtcFromModal = openAtcFromModal
    window.openShareMenu = openShareMenu
    window.closeShareMenu = closeShareMenu
    window.copyShareLink = copyShareLink
    window.eyebrowSwitchCity = eyebrowSwitchCity
    window.toggleEyebrowDropdown = toggleEyebrowDropdown
    window.initPlacesAutocomplete = initPlacesAutocomplete

    // ── Event listeners for static elements ──
    document.querySelectorAll('.cal-filter').forEach(f => {
      f.addEventListener('click', () => {
        document.querySelectorAll('.cal-filter').forEach(x=>x.classList.remove('active'))
        f.classList.add('active'); activeCategory = (f as HTMLElement).dataset.filter||'all'
        if (searchInput) { searchInput.value=''; activeSearch='' }
        if (searchClear) searchClear.style.display='none'
        applyFilters()
      })
    })

    if (searchInput) { searchInput.addEventListener('input', () => applySearch(searchInput.value)) }
    if (searchClear) { searchClear.addEventListener('click', () => { searchInput.value=''; activeSearch=''; showAllDates=false; searchClear.style.display='none'; applyFilters() }) }

    const prevWeek = document.getElementById('cal-prev-week'), nextWeek = document.getElementById('cal-next-week')
    if (nextWeek) nextWeek.addEventListener('click', () => {
      weekOffset++; buildDayChips()
      const d=new Date(today); d.setDate(today.getDate()+weekOffset*7); selectedDate=d; applyDateFilter(d)
      document.querySelectorAll('.cal-filter').forEach(x=>x.classList.remove('active'))
      document.querySelector('.cal-filter[data-filter="all"]')?.classList.add('active')
      const btn=document.getElementById('cal-today-btn') as HTMLButtonElement; if (btn) btn.style.display=weekOffset!==0?'inline-block':'none'
    })
    if (prevWeek) prevWeek.addEventListener('click', () => {
      weekOffset--; buildDayChips()
      const d=new Date(today); d.setDate(today.getDate()+weekOffset*7); selectedDate=d; applyDateFilter(d)
      document.querySelectorAll('.cal-filter').forEach(x=>x.classList.remove('active'))
      document.querySelector('.cal-filter[data-filter="all"]')?.classList.add('active')
      const btn=document.getElementById('cal-today-btn') as HTMLButtonElement; if (btn) btn.style.display=weekOffset!==0?'inline-block':'none'
    })

    const monthToggle = document.getElementById('cal-month-toggle')
    if (monthToggle) monthToggle.addEventListener('click', () => {
      const picker=document.getElementById('cal-month-picker'), btn=monthToggle
      if (!picker) return
      const isOpen = picker.style.display!=='none'
      picker.style.display=isOpen?'none':'block'
      btn.classList.toggle('active',!isOpen)
      if (!isOpen) buildMonthPicker()
    })
    const prevMonth=document.getElementById('cal-prev-month'), nextMonth=document.getElementById('cal-next-month')
    if (prevMonth) prevMonth.addEventListener('click', ()=>{ pickerDate.setMonth(pickerDate.getMonth()-1); buildMonthPicker() })
    if (nextMonth) nextMonth.addEventListener('click', ()=>{ pickerDate.setMonth(pickerDate.getMonth()+1); buildMonthPicker() })

    document.addEventListener('click', (e) => {
      const atcDd=document.getElementById('atc-dropdown'), shareDd=document.getElementById('share-dropdown'), eyebrowDd=document.getElementById('hero-eyebrow-dropdown')
      if (atcDd&&!atcDd.contains(e.target as Node)&&!(e.target as HTMLElement).closest?.('.atc-btn,#modal-atc')) atcDd.classList.remove('open')
      if (shareDd&&!shareDd.contains(e.target as Node)&&(e.target as HTMLElement).id!=='modal-share') shareDd.style.display='none'
      if (eyebrowDd&&!eyebrowDd.contains(e.target as Node)) eyebrowDd.classList.remove('open')
    })
    document.addEventListener('keydown', e => { if (e.key==='Escape') closeEventModal() })

    // Places Autocomplete + radius zip search
    const radiusZipInput = document.getElementById('radius-zip') as HTMLInputElement
    if (radiusZipInput) {
      radiusZipInput.addEventListener('input', () => {
        if (zipTimer) clearTimeout(zipTimer)
        const val=radiusZipInput.value, status=document.getElementById('radius-status') as HTMLElement
        if (val.length<3) { if (status) status.textContent=''; return }
        if (ZIP_COORDS[val.trim()]) {
          const [lat,lng]=ZIP_COORDS[val.trim()]
          userLat=lat; userLng=lng; window.userLat=lat; radiusActive=true
          const sliderWrap=document.getElementById('radius-slider-wrap')
          if (sliderWrap) sliderWrap.style.display='flex'
          if (status) status.textContent=`Showing events within ${radiusMiles} miles`
          applyFilters()
        }
      })
    }

    // Scroll reveal
    const reveals = document.querySelectorAll('.reveal')
    const revealObserver = new IntersectionObserver((entries) => {
      entries.forEach((e, i) => { if (e.isIntersecting) { setTimeout(()=>e.target.classList.add('visible'),i*80); revealObserver.unobserve(e.target) } })
    }, { threshold:0.1 })
    reveals.forEach(el => revealObserver.observe(el))

    // Restore saved location
    try {
      const lat=parseFloat(localStorage.getItem('yoocal_lat')||''), lng=parseFloat(localStorage.getItem('yoocal_lng')||''), city=localStorage.getItem('yoocal_city')
      if (lat&&lng&&city) setConfirmedLocation(city, lat, lng)
    } catch(e) {}

    // Google Places Autocomplete - init when Maps API loads
    if (window.google?.maps) initPlacesAutocomplete()
    window.initPlacesAutocomplete = initPlacesAutocomplete

    // Load initial city
    const initCityKey = new URLSearchParams(window.location.search).get('city')||'parkcity'
    const initChip = document.querySelector(`.loc-chip[data-city="${initCityKey}"]`) as HTMLElement
    if (initChip) initChip.classList.add('active')
    buildDayChips()
    loadCity(initCityKey)
    updateNavLinks(initCityKey)

    return () => {
      delete (window as any).setView; delete (window as any).switchCity
      delete (window as any).openEventModal; delete (window as any).closeEventModal
    }
  }, [])

  return (
    <>
      {/* SEO content hidden from users, visible to crawlers */}
      <div id="seo-content" style={{position:'absolute',width:'1px',height:'1px',overflow:'hidden',clip:'rect(0,0,0,0)',whiteSpace:'nowrap'}}>
        <h1>Yoocal — Things To Do in Park City, Utah</h1>
        <p>Yoocal is Park City&apos;s free local events calendar, updated daily from every source.</p>
        <h2>Park City Events Calendar</h2>
        <p>Find concerts, outdoor adventures, festivals, food events, races, arts events, family activities, and more in Park City, Utah.</p>
        <h2>Elkhart Lake, Wisconsin Events</h2>
        <p>Road America race weekends, live music at Siebkens Resort, events at The Osthoff Resort, and more.</p>
      </div>

      {/* NAV */}
      <nav>
        <a href="/" className="nav-logo"><div className="nav-dot" /> yoocal</a>
        <div className="nav-links">
          <a href="/about" id="nav-about">About</a>
          <a href="/this-weekend" id="nav-weekend" style={{display:'none'}}>This Weekend</a>
          <a href="/venues" id="nav-venues" style={{display:'none'}}>Venues</a>
          <a href="/for-businesses">For businesses</a>
          <a href="https://forms.groupmail.info/subscribe/yoocal" target="_blank" rel="noopener noreferrer" className="nav-cta">Get notified</a>
        </div>
      </nav>

      {/* HERO */}
      <div className="hero-wrapper">

        {/* Confirmed location band */}
        <div className="location-bar" id="location-confirmed-band" style={{display:'none',justifyContent:'space-between'}}>
          <div style={{display:'flex',alignItems:'center',gap:'10px'}}>
            <div style={{width:'8px',height:'8px',borderRadius:'50%',background:'var(--purple-light)',flexShrink:0}} />
            <div>
              <div style={{fontSize:'14px',fontWeight:600,color:'white'}} id="confirmed-city-name">—</div>
              <div style={{fontSize:'11px',color:'rgba(255,255,255,0.4)'}} id="confirmed-radius-label">Showing events nearby</div>
            </div>
          </div>
          <button onClick={() => window.clearHeroLocation?.()} style={{background:'none',border:'1px solid rgba(255,255,255,0.2)',color:'rgba(255,255,255,0.5)',padding:'5px 14px',borderRadius:'100px',fontSize:'12px',cursor:'pointer'}}>Change location</button>
        </div>

        {/* City chips */}
        <div className="location-bar" id="location-city-chips">
          <span className="loc-label">Browse by city</span>
          <a href="/park-city" className="loc-chip" data-city="parkcity">📍 Park City, UT</a>
          <a href="/elkhart-lake" className="loc-chip" data-city="elkhartlake">📍 Elkhart Lake, WI</a>
          <a href="/heber" className="loc-chip" data-city="heber">📍 Heber Valley, UT</a>
          <a href="/jackson-hole" className="loc-chip" data-city="jackson">📍 Jackson Hole, WY</a>
          <a href="#signup" className="loc-chip" style={{opacity:0.5}}>+ Aspen, CO — coming soon</a>
        </div>
      </div>


      {/* CALENDAR (V2 — chips + cards in React state) */}
      <section className="calendar-section" id="events" style={{textAlign:'center'}}>
        <h2 style={{fontSize:'clamp(48px, 7vw, 80px)',lineHeight:1.05}}>What&apos;s happening <em>now</em></h2>
        <p style={{marginBottom:'40px',marginTop:'12px',fontSize:'18px',color:'rgba(255,255,255,0.7)'}}>{cityDisplayName} — updated daily</p>
        <div style={{maxWidth:1100,margin:'0 auto',padding:'0 16px',textAlign:'left'}}>
          <EventsV2Embedded />
        </div>
      </section>


      {/* EMAIL SIGNUP */}
      <section className="signup-section" id="signup">
        <h2>Get &quot;This Weekend in Park City&quot; every Thursday</h2>
        <p>The only email you need to plan your weekend. Free, local, always relevant.</p>
        <form className="signup-form" onSubmit={(e) => { e.preventDefault(); window.location.href='https://forms.groupmail.info/subscribe/yoocal' }}>
          <input type="email" placeholder="your@email.com" required id="email-input" />
          <button type="submit">Notify me</button>
        </form>
        <p className="signup-note">No spam. Unsubscribe anytime.</p>
      </section>

      {/* FOR BUSINESSES */}
      <section className="biz-section" id="business">
        <div className="section-label">For businesses</div>
        <h2>Get your events <em>found</em></h2>
        <p style={{fontSize:'17px',color:'var(--muted)',maxWidth:'480px',lineHeight:1.7,fontWeight:300,marginBottom:0}}>List your events free, or get featured placement in front of everyone looking for things to do.</p>
        <div className="biz-cards" style={{marginTop:'48px'}}>
          <div className="biz-card reveal">
            <div className="biz-price">Free</div>
            <div className="biz-name">Basic listing</div>
            <div className="biz-desc">Your events automatically pulled from public sources, or submit manually.</div>
            <ul className="biz-features"><li>Event listed in the calendar</li><li>Links to your registration page</li><li>Category &amp; date filtering</li><li>Sourced &amp; attributed to you</li></ul>
            <a href="/submit" className="biz-btn">Submit your event</a>
          </div>
          <div className="biz-card featured-card reveal">
            <div className="biz-price">$0.99<span>/day</span></div>
            <div className="biz-name">Featured placement</div>
            <div className="biz-desc">Pin your events to the top of the calendar with a Featured badge on your event day.</div>
            <ul className="biz-features"><li>Top-of-calendar placement</li><li>⭐ Featured badge on your events</li><li>Priority in newsletter</li><li>Cancel any time</li></ul>
            <a href="mailto:hello@yoocal.com" className="biz-btn">Get featured →</a>
          </div>
          <div className="biz-card reveal">
            <div className="biz-price">$9.99<span>/day</span></div>
            <div className="biz-name">Partner sponsor</div>
            <div className="biz-desc">Category sponsorship and newsletter placement for maximum visibility.</div>
            <ul className="biz-features"><li>Category sponsorship</li><li>Weekly newsletter slot</li><li>Featured badge on all events</li><li>Monthly performance report</li><li>Cancel any time</li></ul>
            <a href="mailto:hello@yoocal.com" className="biz-btn">Contact us →</a>
          </div>
        </div>
      </section>

      {/* FOOTER */}
      <footer>
        <div className="footer-top">
          <div>
            <a href="#" className="footer-logo"><div className="nav-dot" /> yoocal</a>
            <div className="footer-tagline">Your local, everywhere.</div>
          </div>
          <div className="footer-links">
            <div className="footer-col"><h4>Product</h4><a href="#events">Browse events</a><a href="#signup">Newsletter</a></div>
            <div className="footer-col"><h4>Business</h4><a href="#business">List your event</a><a href="mailto:hello@yoocal.com">Advertise</a><a href="mailto:hello@yoocal.com">Partner with us</a></div>
            <div className="footer-col"><h4>Cities</h4><a href="/park-city">Park City, UT</a><a href="/heber">Heber Valley, UT</a><a href="/elkhart-lake">Elkhart Lake, WI</a><a href="/jackson-hole">Jackson Hole, WY</a><a href="#signup">Aspen, CO (soon)</a></div>
          </div>
        </div>
        <div className="footer-bottom"><span>© 2026 Yoocal. All rights reserved.</span><span>hello@yoocal.com</span></div>
      </footer>

      {/* EVENT MODAL */}
      <div id="event-modal-overlay" onClick={() => window.closeEventModal?.()} style={{display:'none',position:'fixed',inset:0,background:'rgba(10,8,30,0.75)',zIndex:10000,backdropFilter:'blur(4px)'}} />
      <div id="event-modal" style={{display:'none',position:'fixed',top:'50%',left:'50%',transform:'translate(-50%,-50%)',zIndex:10001,width:'min(560px, 92vw)',maxHeight:'85vh',overflowY:'auto',background:'#1e1b3a',borderRadius:'20px',border:'1px solid rgba(255,255,255,0.1)',boxShadow:'0 24px 80px rgba(0,0,0,0.5)'}}>
        <div style={{padding:'28px 28px 0'}}>
          <div style={{display:'flex',alignItems:'flex-start',justifyContent:'space-between',gap:'12px',marginBottom:'18px'}}>
            <div id="modal-tags" style={{display:'flex',gap:'6px',flexWrap:'wrap'}} />
            <button onClick={() => window.closeEventModal?.()} style={{background:'rgba(255,255,255,0.08)',border:'none',color:'rgba(255,255,255,0.6)',width:'32px',height:'32px',borderRadius:'50%',cursor:'pointer',fontSize:'18px',flexShrink:0,display:'flex',alignItems:'center',justifyContent:'center'}}>×</button>
          </div>
          <h2 id="modal-title" style={{fontFamily:"'DM Serif Display',serif",fontSize:'clamp(20px,4vw,28px)',color:'white',lineHeight:1.2,marginBottom:'16px'}} />
          <div id="modal-meta" style={{display:'flex',flexDirection:'column',gap:'10px',marginBottom:'20px'}} />
          <p id="modal-desc" style={{fontSize:'15px',color:'rgba(255,255,255,0.55)',lineHeight:1.8,marginBottom:'24px'}} />
        </div>
        <div style={{padding:'0 28px 28px',display:'flex',gap:'10px',flexWrap:'wrap'}}>
          <a id="modal-link" href="#" target="_blank" rel="noopener noreferrer" style={{display:'inline-flex',alignItems:'center',gap:'8px',background:'var(--purple)',color:'white',padding:'12px 24px',borderRadius:'100px',fontSize:'14px',fontWeight:600,textDecoration:'none'}}>View full details ↗</a>
          <button id="modal-atc" onClick={() => window.openAtcFromModal?.()} style={{display:'inline-flex',alignItems:'center',gap:'8px',background:'rgba(255,255,255,0.07)',border:'1px solid rgba(255,255,255,0.15)',color:'white',padding:'12px 24px',borderRadius:'100px',fontSize:'14px',fontWeight:600,cursor:'pointer'}}>📅 Add to calendar</button>
          <button id="modal-share" onClick={(e) => window.openShareMenu?.(e.nativeEvent)} style={{display:'inline-flex',alignItems:'center',gap:'8px',background:'rgba(255,255,255,0.07)',border:'1px solid rgba(255,255,255,0.15)',color:'white',padding:'12px 24px',borderRadius:'100px',fontSize:'14px',fontWeight:600,cursor:'pointer'}}>↗ Share</button>
        </div>
      </div>

      {/* ATC DROPDOWN */}
      <div className="atc-dropdown" id="atc-dropdown">
        <a className="atc-option" id="atc-google" href="#" target="_blank" rel="noopener noreferrer" onClick={() => document.getElementById('atc-dropdown')?.classList.remove('open')}>📅 Google Calendar</a>
        <a className="atc-option" id="atc-apple" href="#" download onClick={() => document.getElementById('atc-dropdown')?.classList.remove('open')}>🍎 Apple Calendar</a>
        <a className="atc-option" id="atc-outlook" href="#" download onClick={() => document.getElementById('atc-dropdown')?.classList.remove('open')}>📧 Outlook / Other</a>
      </div>

      {/* SHARE DROPDOWN */}
      <div id="share-dropdown" style={{display:'none',position:'fixed',background:'white',borderRadius:'14px',boxShadow:'0 8px 32px rgba(0,0,0,0.25)',padding:'8px',zIndex:20000,minWidth:'200px'}}>
        <a id="share-native" className="atc-option" href="#" style={{display:'none'}}>📱 Share...</a>
        <a id="share-sms" className="atc-option" href="#">💬 Text message</a>
        <a id="share-email" className="atc-option" href="#">✉️ Email</a>
        <a id="share-x" className="atc-option" href="#" target="_blank" rel="noopener noreferrer">𝕏 X / Twitter</a>
        <a id="share-facebook" className="atc-option" href="#" target="_blank" rel="noopener noreferrer">📘 Facebook</a>
        <a id="share-copy" className="atc-option" href="#" onClick={(e) => window.copyShareLink?.(e.nativeEvent)}>🔗 Copy link</a>
      </div>

      {/* EYEBROW DROPDOWN */}
      <div className="hero-eyebrow-dropdown" id="hero-eyebrow-dropdown">
        <div className="eyebrow-city-option active" id="eyebrow-opt-parkcity" onClick={(e) => window.eyebrowSwitchCity?.(e.nativeEvent,'parkcity')}>📍 Park City, UT</div>
        <div className="eyebrow-city-option" id="eyebrow-opt-elkhartlake" onClick={(e) => window.eyebrowSwitchCity?.(e.nativeEvent,'elkhartlake')}>📍 Elkhart Lake, WI</div>
        <div className="eyebrow-city-option" id="eyebrow-opt-heber" onClick={(e) => window.eyebrowSwitchCity?.(e.nativeEvent,'heber')}>📍 Heber Valley, UT</div>
        <div className="eyebrow-dropdown-divider" />
        <div className="eyebrow-city-option" id="eyebrow-opt-jackson" onClick={(e) => window.eyebrowSwitchCity?.(e.nativeEvent,'jackson')}>📍 Jackson Hole, WY</div>
        <div className="eyebrow-city-option coming-soon">+ Aspen, CO — coming soon</div>
      </div>
    </>
  )
}
