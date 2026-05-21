'use client'

import { useEffect, useMemo, useState } from 'react'
import EventModal, { type EventModalData } from './EventModal'
import SiteNav from './SiteNav'

// ============================================================
// Types
// ============================================================

interface YocEvent {
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
  source_url?: string
  image_url?: string
  categories?: string[]
  facets?: string[]
  hook?: string
  is_free?: boolean | null
  price?: string
}

interface CityConfig {
  key: string
  name: string
  label: string
  file: string
  lat: number
  lng: number
}

// ============================================================
// Configuration
// ============================================================

const CITIES: Record<string, CityConfig> = {
  parkcity: {
    key: 'parkcity', name: 'Park City, UT',
    label: 'Park City & Summit County',
    file: '/events.json', lat: 40.6461, lng: -111.498,
  },
  heber: {
    key: 'heber', name: 'Heber Valley, UT',
    label: 'Heber Valley',
    file: '/events-heber.json', lat: 40.5071, lng: -111.4133,
  },
  jackson: {
    key: 'jackson', name: 'Jackson Hole, WY',
    label: 'Jackson Hole',
    file: '/events-jackson.json', lat: 43.4799, lng: -110.7624,
  },
  elkhartlake: {
    key: 'elkhartlake', name: 'Elkhart Lake, WI',
    label: 'Elkhart Lake',
    file: '/events-elkhartlake.json', lat: 43.8358, lng: -88.0051,
  },
}

const ALL_CATEGORIES = [
  'Music', 'Food & Drink', 'Outdoor', 'Family', 'Arts', 'Theater', 'Film',
  'Sports', 'Kids', 'Wellness', 'Education', 'Festival', 'Government', 'Community',
]

const PRIMARY_CATEGORIES = ['Music', 'Food & Drink', 'Outdoor', 'Family']

// Category colors — saturated enough to read, calm enough to coexist
const CATEGORY_COLORS: Record<string, { bg: string; fg: string }> = {
  Music:          { bg: '#EEEDFE', fg: '#534AB7' },  // purple (brand)
  'Food & Drink': { bg: '#FAEEDA', fg: '#B45309' },  // amber (brand)
  Arts:           { bg: '#FCE7F3', fg: '#9D174D' },  // pink
  Theater:        { bg: '#EDE9FE', fg: '#5B21B6' },  // violet
  Film:           { bg: '#E0E7FF', fg: '#3730A3' },  // indigo
  Sports:         { bg: '#DBEAFE', fg: '#1E40AF' },  // blue
  Outdoor:        { bg: '#D1FAE5', fg: '#065F46' },  // emerald
  Family:         { bg: '#FFEDD5', fg: '#9A3412' },  // orange
  Kids:           { bg: '#FEF3C7', fg: '#92400E' },  // amber-dark
  Wellness:       { bg: '#CCFBF1', fg: '#115E59' },  // teal
  Education:      { bg: '#FEF9C3', fg: '#854D0E' },  // yellow
  Festival:       { bg: '#FEE2E2', fg: '#991B1B' },  // red
  Government:     { bg: '#F1F5F9', fg: '#334155' },  // slate
  Community:      { bg: '#F3E8FF', fg: '#6B21A8' },  // purple-light
}

const FACET_COLORS: Record<string, { bg: string; fg: string }> = {
  Free:      { bg: '#D1FAE5', fg: '#065F46' },
  '21+':     { bg: '#F1F5F9', fg: '#334155' },
  Paid:      { bg: '#F1F5F9', fg: '#334155' },
  'Drop-in': { bg: '#F1F5F9', fg: '#334155' },
}

// ============================================================
// Filter types
// ============================================================

type DayFilter = 'all' | 'today' | 'tomorrow' | 'weekend' | '7days' | 'pickdate'
type TimeFilter = 'any' | 'morning' | 'afternoon' | 'evening' | 'latenight'

// ============================================================
// Utilities
// ============================================================

const MOUNTAIN_OFFSET = -6

function todayMountain(): Date {
  const now = new Date()
  const utc = now.getTime() + now.getTimezoneOffset() * 60000
  return new Date(utc + MOUNTAIN_OFFSET * 3600000)
}

function dateToStr(d: Date): string {
  return d.toISOString().slice(0, 10)
}

function parseEventDate(s: string | undefined): Date | null {
  if (!s) return null
  const m = s.match(/^(\d{4})-(\d{2})-(\d{2})/)
  if (!m) return null
  return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]))
}

function parseTime12h(t: string | undefined): number | null {
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

function formatTimeDisplay(t: string | undefined): { hour: string; period: string } {
  if (!t) return { hour: '--', period: '' }
  const m = t.trim().match(/^(\d{1,2}):?(\d{2})?\s*(AM|PM)?$/i)
  if (!m) return { hour: t, period: '' }
  const h = m[1]
  const mn = m[2] || '00'
  const ampm = (m[3] || '').toUpperCase()
  return { hour: `${h}:${mn}`, period: ampm }
}

function weekendDates(): { start: Date; end: Date } {
  const t = todayMountain()
  const dow = t.getDay()
  let daysToFri = (5 - dow + 7) % 7
  if (dow === 5) daysToFri = 0
  const start = new Date(t)
  start.setDate(t.getDate() + daysToFri)
  const end = new Date(start)
  end.setDate(start.getDate() + 2)
  return { start, end }
}

// ============================================================
// Chip components (using yoocal brand colors)
// ============================================================

function Chip({
  active, onClick, children, color, compact = false,
}: {
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
    background: '#fff',
    color: '#2d2b3d',
    border: '1px solid rgba(83,74,183,0.18)',
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

function CategoryPill({ name, role = 'category' }: { name: string; role?: 'category' | 'facet' }) {
  const colors = role === 'category' ? CATEGORY_COLORS[name] : FACET_COLORS[name]
  const fallback = { bg: '#F1F5F9', fg: '#334155' }
  const { bg, fg } = colors || fallback
  return (
    <span style={{
      background: bg, color: fg,
      fontSize: 11, padding: '2px 9px', borderRadius: 999,
      fontWeight: 600,
      fontFamily: "'DM Sans', sans-serif",
    }}>{name}</span>
  )
}

function EventCard({ event, onClick }: { event: YocEvent; onClick: () => void }) {
  const date = parseEventDate(event.date)
  const dayOfWeek = date ? ['SUN','MON','TUE','WED','THU','FRI','SAT'][date.getDay()] : '?'
  const time = formatTimeDisplay(event.start_time)
  
  return (
    <button
      onClick={onClick}
      style={{
        width: '100%',
        textAlign: 'left',
        background: '#fff',
        border: '1px solid rgba(83,74,183,0.12)',
        borderRadius: 14,
        padding: '14px 16px',
        display: 'flex',
        gap: 14,
        alignItems: 'flex-start',
        marginBottom: 10,
        cursor: 'pointer',
        fontFamily: "'DM Sans', sans-serif",
        transition: 'all 0.15s ease',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = 'rgba(83,74,183,0.35)'
        e.currentTarget.style.transform = 'translateY(-1px)'
        e.currentTarget.style.boxShadow = '0 4px 12px rgba(83,74,183,0.08)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = 'rgba(83,74,183,0.12)'
        e.currentTarget.style.transform = 'translateY(0)'
        e.currentTarget.style.boxShadow = 'none'
      }}
    >
      <div style={{
        background: '#EEEDFE',
        borderRadius: 10,
        padding: '10px 14px',
        textAlign: 'center',
        minWidth: 64,
        flexShrink: 0,
      }}>
        <div style={{ fontSize: 11, color: '#534AB7', marginBottom: 2, fontWeight: 600, letterSpacing: 0.5 }}>{dayOfWeek}</div>
        <div style={{ fontSize: 18, fontWeight: 600, color: '#1a1830' }}>{time.hour}</div>
        <div style={{ fontSize: 10, color: '#6b6880' }}>{time.period}</div>
      </div>
      
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontWeight: 600, fontSize: 15, color: '#1a1830', marginBottom: 4 }}>
          {event.title}
        </div>
        
        {event.hook && (
          <div style={{ fontSize: 13, color: '#534AB7', marginBottom: 6, fontStyle: 'italic' }}>
            {event.hook}
          </div>
        )}
        
        <div style={{
          fontSize: 12, color: '#6b6880', marginBottom: 6,
          display: 'flex', gap: 12, flexWrap: 'wrap',
        }}>
          {event.start_time && (
            <span>{event.start_time}{event.end_time ? ` – ${event.end_time}` : ''}</span>
          )}
          {event.facets?.includes('Paid') && <span>Tickets req'd</span>}
          {event.facets?.includes('21+') && <span>21+</span>}
        </div>
        
        {(event.venue_name || event.location) && (
          <div style={{ fontSize: 12, color: '#6b6880', marginBottom: 8 }}>
            {event.venue_name || event.location}
          </div>
        )}
        
        <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
          {(event.categories || []).map(c => <CategoryPill key={c} name={c} role="category" />)}
          {(event.facets || []).map(f => <CategoryPill key={f} name={f} role="facet" />)}
        </div>
      </div>
    </button>
  )
}

// ============================================================
// Main component
// ============================================================

export default function CalendarClientV2({ initialCity = 'parkcity' }: { initialCity?: string }) {
  const [cityKey, setCityKey] = useState(initialCity)
  const [events, setEvents] = useState<YocEvent[]>([])
  const [loading, setLoading] = useState(true)
  
  const [dayFilter, setDayFilter] = useState<DayFilter>('today')
  const [timeFilter, setTimeFilter] = useState<TimeFilter>('any')
  const [activeCategory, setActiveCategory] = useState<string>('all')
  const [showAllCategories, setShowAllCategories] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [pickedDate, setPickedDate] = useState<string>(dateToStr(todayMountain()))
  const [selectedEvent, setSelectedEvent] = useState<EventModalData | null>(null)
  
  const city = CITIES[cityKey]
  
  useEffect(() => {
    setLoading(true)
    fetch(city.file)
      .then(r => r.json())
      .then(d => {
        const evts = (d.events || d) as YocEvent[]
        setEvents(evts)
        setLoading(false)
      })
      .catch(e => {
        console.error('Failed to load events:', e)
        setLoading(false)
      })
  }, [city.file])
  
  const filteredEvents = useMemo(() => {
    let result = events
    const today = todayMountain()
    const todayStr = dateToStr(today)
    
    result = result.filter(e => (e.date || '') >= todayStr)
    
    if (dayFilter === 'today') {
      result = result.filter(e => e.date === todayStr)
    } else if (dayFilter === 'tomorrow') {
      const tom = new Date(today)
      tom.setDate(today.getDate() + 1)
      const tomStr = dateToStr(tom)
      result = result.filter(e => e.date === tomStr)
    } else if (dayFilter === 'weekend') {
      const { start, end } = weekendDates()
      const startStr = dateToStr(start)
      const endStr = dateToStr(end)
      result = result.filter(e => e.date && e.date >= startStr && e.date <= endStr)
    } else if (dayFilter === '7days') {
      const week = new Date(today)
      week.setDate(today.getDate() + 7)
      const weekStr = dateToStr(week)
      result = result.filter(e => e.date && e.date >= todayStr && e.date <= weekStr)
    } else if (dayFilter === 'pickdate') {
      result = result.filter(e => e.date === pickedDate)
    }
    
    if (timeFilter !== 'any') {
      result = result.filter(e => {
        const t = parseTime12h(e.start_time)
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
    
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase()
      result = result.filter(e => {
        const text = [
          e.title, e.description, e.venue_name, e.location, e.address,
          e.source, ...(e.categories || []), ...(e.facets || [])
        ].filter(Boolean).join(' ').toLowerCase()
        return text.includes(q)
      })
    }
    
    result.sort((a, b) => {
      if (a.date !== b.date) return (a.date || '').localeCompare(b.date || '')
      const ta = parseTime12h(a.start_time) ?? 24 * 60
      const tb = parseTime12h(b.start_time) ?? 24 * 60
      return ta - tb
    })
    
    return result
  }, [events, dayFilter, timeFilter, activeCategory, searchQuery, pickedDate])
  
  const todayDow = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'][todayMountain().getDay()]
  
  const handleEventClick = (ev: YocEvent) => {
    setSelectedEvent({
      title: ev.title,
      date: ev.date,
      end_date: ev.end_date,
      start_time: ev.start_time,
      end_time: ev.end_time,
      location: ev.venue_name || ev.location,
      description: ev.description,
      link: ev.link,
      source: ev.source,
      is_free: ev.is_free,
      price: ev.price,
      categories: ev.categories,
    })
  }
  
  return (
    <>
      <SiteNav cityKey={cityKey as any} />
      <div style={{
        minHeight: '100vh',
        background: '#faf9ff',
        paddingTop: 88,
        paddingBottom: 80,
      }}>
        <div style={{
          maxWidth: 880,
          margin: '0 auto',
          padding: '0 16px',
          fontFamily: "'DM Sans', sans-serif",
          color: '#2d2b3d',
        }}>
      <div style={{
        background: '#fff',
        border: '1px solid rgba(83,74,183,0.12)',
        borderRadius: 16,
        padding: 18,
        marginBottom: 18,
        boxShadow: '0 1px 3px rgba(83,74,183,0.04)',
      }}>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 16 }}>
          <select
            value={cityKey}
            onChange={(e) => setCityKey(e.target.value)}
            style={{
              padding: '9px 14px', fontSize: 14, fontWeight: 600,
              border: '1px solid rgba(83,74,183,0.18)', borderRadius: 10, background: '#fff',
              cursor: 'pointer', color: '#1a1830',
              fontFamily: "'DM Sans', sans-serif",
            }}
          >
            {Object.values(CITIES).map(c => (
              <option key={c.key} value={c.key}>{c.name}</option>
            ))}
          </select>
          <input
            type="text"
            placeholder="Search bands, venues, or what to do..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              flex: 1, padding: '9px 14px', fontSize: 14,
              border: '1px solid rgba(83,74,183,0.18)', borderRadius: 10,
              fontFamily: "'DM Sans', sans-serif",
              color: '#1a1830',
            }}
          />
        </div>
        
        <div style={{ display: 'flex', gap: 6, marginBottom: 12, overflowX: 'auto', alignItems: 'center' }}>
          <span style={{ fontSize: 12, color: '#6b6880', minWidth: 56, fontWeight: 600 }}>When:</span>
          <Chip active={dayFilter === 'all'} onClick={() => setDayFilter('all')}>All upcoming</Chip>
          <Chip active={dayFilter === 'today'} onClick={() => setDayFilter('today')}>Today · {todayDow}</Chip>
          <Chip active={dayFilter === 'tomorrow'} onClick={() => setDayFilter('tomorrow')}>Tomorrow</Chip>
          <Chip active={dayFilter === 'weekend'} onClick={() => setDayFilter('weekend')}>This weekend</Chip>
          <Chip active={dayFilter === '7days'} onClick={() => setDayFilter('7days')}>Next 7 days</Chip>
          <Chip active={dayFilter === 'pickdate'} onClick={() => setDayFilter('pickdate')}>Pick date</Chip>
          {dayFilter === 'pickdate' && (
            <input
              type="date"
              value={pickedDate}
              onChange={(e) => setPickedDate(e.target.value)}
              style={{ padding: '6px 10px', fontSize: 13, borderRadius: 8, border: '1px solid rgba(83,74,183,0.18)' }}
            />
          )}
        </div>
        
        <div style={{ display: 'flex', gap: 6, marginBottom: 12, overflowX: 'auto', alignItems: 'center' }}>
          <span style={{ fontSize: 12, color: '#6b6880', minWidth: 56, fontWeight: 600 }}>Time:</span>
          <Chip compact active={timeFilter === 'any'} onClick={() => setTimeFilter('any')}>Any time</Chip>
          <Chip compact active={timeFilter === 'morning'} onClick={() => setTimeFilter('morning')}>Morning</Chip>
          <Chip compact active={timeFilter === 'afternoon'} onClick={() => setTimeFilter('afternoon')}>Afternoon</Chip>
          <Chip compact active={timeFilter === 'evening'} onClick={() => setTimeFilter('evening')}>Evening</Chip>
          <Chip compact active={timeFilter === 'latenight'} onClick={() => setTimeFilter('latenight')}>Late night</Chip>
        </div>
        
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
          <span style={{ fontSize: 12, color: '#6b6880', minWidth: 56, fontWeight: 600 }}>Vibe:</span>
          <Chip compact active={activeCategory === 'all'} onClick={() => setActiveCategory('all')}>
            All categories
          </Chip>
          {(showAllCategories ? ALL_CATEGORIES : PRIMARY_CATEGORIES).map(cat => (
            <Chip
              key={cat}
              compact
              active={activeCategory === cat}
              onClick={() => setActiveCategory(cat)}
              color={activeCategory === cat ? CATEGORY_COLORS[cat] : undefined}
            >
              {cat}
            </Chip>
          ))}
          {!showAllCategories && (
            <button
              onClick={() => setShowAllCategories(true)}
              style={{
                padding: '5px 12px', fontSize: 12, borderRadius: 999,
                background: '#fff', color: '#6b6880',
                border: '1px solid rgba(83,74,183,0.18)', cursor: 'pointer',
                fontFamily: "'DM Sans', sans-serif",
              }}
            >
              + {ALL_CATEGORIES.length - PRIMARY_CATEGORIES.length} more
            </button>
          )}
        </div>
      </div>
      
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        margin: '0 4px 14px', fontSize: 13, color: '#6b6880',
      }}>
        <div>
          <strong style={{ color: '#1a1830', fontWeight: 600 }}>
            {filteredEvents.length} event{filteredEvents.length !== 1 ? 's' : ''}
          </strong>
          {' · '}{city.label}
        </div>
      </div>
      
      {loading ? (
        <div style={{ textAlign: 'center', padding: 60, color: '#6b6880' }}>Loading events...</div>
      ) : filteredEvents.length === 0 ? (
        <div style={{ textAlign: 'center', padding: 60, color: '#6b6880', background: '#fff', borderRadius: 14, border: '1px solid rgba(83,74,183,0.12)' }}>
          No events match your filters. Try widening the time range or clearing search.
        </div>
      ) : (
        <div>
          {filteredEvents.map((ev, i) => (
            <EventCard key={`${ev.title}-${ev.date}-${i}`} event={ev} onClick={() => handleEventClick(ev)} />
          ))}
        </div>
      )}
      
        <EventModal event={selectedEvent} onClose={() => setSelectedEvent(null)} />
        </div>
      </div>
    </>
  )
}
