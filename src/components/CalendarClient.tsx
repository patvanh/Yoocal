'use client'

import CitySearch from "@/components/CitySearch"
import RadiusPicker from "@/components/RadiusPicker"
import { useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useSearchParams } from 'next/navigation'
import dynamic from 'next/dynamic'
import { type EventModalData } from './EventModal'
const EventModal = dynamic(() => import('./EventModal'), { ssr: false })
import { Music, UtensilsCrossed, Drama, Trees, Trophy, Users, MoreHorizontal, CalendarDays } from 'lucide-react'
import MoreTile from '@/components/MoreTile'

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
  _time_uncertain?: boolean
  _conflicts?: Record<string, { value: string; source: string }[]>
  _source_links?: { url: string; source: string }[]
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
  // Cross-city search tag: set on events from cities OTHER than the current
  // one (Model C). Used to filter by city pill and display city attribution.
  _sourceCity?: string
  // Fields populated by build_master_and_views.py / scrapers that the
  // interface didn't previously declare. Same class as the image_url fix
  // earlier today — TS strictness fires when code reads these.
  recurrence?: string
  recurrence_day?: string
  recurrence_days?: string
  recurrence_text?: string
  occurrence_dates?: string[]
  date_label?: string
  source_url?: string
  scraped_at?: string
  _distance_mi?: number
}

// Search match: case-insensitive substring across title, description, venue,
// location, address, source, AND every category-ish field (categories,
// filter_categories, facets). Including filter_categories matters because that's
// where the clean user-facing buckets live ("Running & Races", "Outdoors"...) —
// without it, typing "running" misses everything tagged via the bucket pipeline.
// Synonym table for search. When a user searches a key, the search also
// matches events containing any synonym. Keeps existing behavior (exact word
// still wins) AND broadens results so "concert" finds music events even when
// the literal word "concert" isn't in the data.
//
// Conservative: only obvious "same concept, different word" cases. Expand as
// real user misses surface.
const SEARCH_SYNONYMS: Record<string, string[]> = {
  concert: ['music', 'band', 'live', 'perform', 'jazz', 'rock', 'country', 'bluegrass', 'reggae', 'blues', 'acoustic', 'folk', 'indie', 'singer', 'sing'],
  music: ['concert', 'band', 'live', 'perform', 'jazz'],
  race: ['run', 'marathon', '5k', '10k', 'triathlon', 'relay', 'cycling'],
  running: ['run', 'race', 'marathon', '5k', '10k', 'jog'],
  show: ['performance', 'theatre', 'theater', 'exhibit', 'play'],
  theater: ['theatre', 'show', 'performance', 'play'],
  theatre: ['theater', 'show', 'performance', 'play'],
  kids: ['family', 'child', 'children', 'youth', 'baby', 'parent', 'school', 'storytime'],
  family: ['kids', 'child', 'children', 'youth'],
  food: ['drink', 'wine', 'beer', 'dine', 'eat', 'taste', 'market', 'brewery', 'cocktail'],
  hike: ['hiking', 'trail', 'outdoor', 'nature'],
  hiking: ['hike', 'trail', 'outdoor', 'nature'],
  bike: ['biking', 'cycling', 'mountain bike', 'mtb', 'trail'],
  biking: ['bike', 'cycling', 'mtb'],
  art: ['gallery', 'exhibit', 'paint', 'sculpt', 'craft'],
  arts: ['art', 'gallery', 'exhibit', 'theater', 'theatre', 'dance'],
  yoga: ['wellness', 'mindful', 'meditation', 'pilates'],
  free: ['no charge', 'no cost', 'complimentary'],
}

// Word-boundary regex cache so we don't recompile on every event.
const _wordRegexCache = new Map<string, RegExp>()
function _wordRegex(w: string): RegExp {
  let r = _wordRegexCache.get(w)
  if (!r) {
    // Escape regex special chars, then wrap in word boundaries.
    const esc = w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    r = new RegExp(`\\b${esc}\\b`)
    _wordRegexCache.set(w, r)
  }
  return r
}

// Fold accents (\u00e9 -> e) and strip punctuation (apostrophes, hyphens, etc.)
// so search matches regardless of how the user types it. "miners day" matches
// "Miner's Day"; "cafe" matches "Café"; "howloween" matches "Howl-O-Ween".
function _searchNormalize(s: string): string {
  return (s || '')
    .toLowerCase()
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '')  // strip diacritics
    .replace(/[^a-z0-9\s]/g, '')                          // drop punctuation
    .replace(/\s+/g, ' ')
    .trim()
}

function matchesQuery(e: V2YocEvent, qLower: string): boolean {
  if (!qLower) return true
  const text = _searchNormalize([
    e.title, e.description, e.venue_name, e.location, e.address, e.source,
    ...(e.categories || []), ...(e.filter_categories || []), ...(e.facets || [])
  ].filter(Boolean).join(' '))
  // Tokenize the query and require ALL tokens to appear somewhere in the
  // searchable text. Lets "running 5k" match titles like "Park City Trail
  // Series 5K" (contains both "running"-related categories and "5k") even
  // when the literal phrase "running 5k" never appears verbatim.
  const tokens = _searchNormalize(qLower).split(/\s+/).filter(Boolean)
  if (tokens.length === 0) return true
  // Each token matches if it appears literally OR if any of its synonyms
  // does. Synonym lookup is prefix-aware: typing "concer" still matches
  // "concert" synonyms because "concert".startsWith("concer"). Synonym text
  // matched with word boundaries to avoid "rock" hitting "rocky mountain".
  // Strip a trailing 's' for stem-style comparison. "runs" -> "run",
  // "concerts" -> "concert", "races" -> "race". Naive but covers the
  // English plural case which is what users actually type.
  const _stem = (s: string) => s.endsWith('s') && s.length > 2 ? s.slice(0, -1) : s
  return tokens.every(tok => {
    if (text.includes(tok)) return true
    const tokStem = _stem(tok)
    // Plural query -> singular match: "5ks" -> "5k", "concerts" -> "concert".
    // The literal check above misses these; try the stemmed token directly
    // against the text before falling through to synonyms.
    if (tokStem !== tok && tokStem.length >= 2 && text.includes(tokStem)) return true
    // Find all synonym keys that match the user's token via prefix or stem.
    // "conc" -> "concert" key (prefix). "concerts" -> "concert" (stem).
    // "runs" -> "running" (both stem to a shared prefix "run").
    for (const key of Object.keys(SEARCH_SYNONYMS)) {
      const keyStem = _stem(key)
      if (
        !key.startsWith(tok) &&
        !tok.startsWith(key) &&
        !keyStem.startsWith(tokStem) &&
        !tokStem.startsWith(keyStem)
      ) continue
      const syns = SEARCH_SYNONYMS[key]
      if (syns.some(s => _wordRegex(s).test(text))) return true
    }
    return false
  })
}

function isFreeEvent(e: V2YocEvent): boolean {
  if (e.is_free === true) return true
  if (e.is_free === false) return false
  // is_free unknown: infer carefully. A real price ALWAYS wins (overrides any
  // stray "free" wording). A bare "free" in the description is unreliable —
  // wellness/yoga copy is full of "free your mind", "stress-free",
  // "judgment-free" — so we do NOT match it. Only an explicit free price field,
  // a "free" in the TITLE, or a tight free phrase counts.
  const price = (e.price || '').trim().toLowerCase()
  if (['free', '$0', '0', 'no charge', 'no cost', 'free admission', 'free entry'].includes(price)) return true
  if (/\$|\d/.test(price)) return false
  if (/\bfree\b/.test((e.title || '').toLowerCase())) return true
  const desc = (e.description || '').toLowerCase()
  if (/\bfree (admission|entry|event|to attend|and open|to the public)\b/.test(desc)) return true
  if (/\bno (charge|cost|admission fee)\b/.test(desc)) return true
  return false
}

type ChipId = 'weekend' | 'today' | 'free' | 'pickdate' | 'tomorrow' | 'next7' | 'music' | 'outdoors' | 'food' | 'family' | 'arts' | 'sports' | 'kids' | 'wellness' | 'education' | 'festivals'

// Shared date-occurrence helpers (used by both the main-view filter and the
// search-results filter). Pure: event + date strings in, boolean out.
function occursOn(e: V2YocEvent, dayStr: string): boolean {
  const start = e.date || ''
  const end = e.end_date || start
  return start <= dayStr && dayStr <= end
}
function occursInRange(e: V2YocEvent, rangeStart: string, rangeEnd: string): boolean {
  const start = e.date || ''
  const end = e.end_date || start
  return start <= rangeEnd && end >= rangeStart  // range overlap
}

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
    const fri = new Date(sat); fri.setDate(sat.getDate() - 1)
    const sun = new Date(sat); sun.setDate(sat.getDate() + 1)
    const fmt = (x: Date) => `${x.getFullYear()}-${String(x.getMonth()+1).padStart(2,'0')}-${String(x.getDate()).padStart(2,'0')}`
    return onDay(fmt(fri)) || onDay(fmt(sat)) || onDay(fmt(sun))
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
  greenlake: { lat: 43.8408, lng: -88.9576 },
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

// These MUST match the filter_categories buckets the build pipeline produces
// (see build_master_and_views.py / category_normalizer.py). The Vibe filter
// matches an event's filter_categories against these, so any mismatch (e.g.
// 'Outdoor' vs 'Outdoors') silently filters out everything in that bucket.
const V2_ALL_CATEGORIES = [
  'Music', 'Food & Drink', 'Arts & Theater', 'Outdoors', 'Sports',
  'Running & Races', 'Family & Kids', 'Wellness', 'Education & Talks', 'Community',
]
const V2_PRIMARY_CATEGORIES = ['Music', 'Food & Drink', 'Outdoor', 'Family']
// Hero category tiles: display label + the EXACT filter_categories value that
// drives activeCategories filtering (see line ~1078). 'Family' shows short but
// filters on 'Family & Kids'. Icons from lucide-react.
const V2_CATEGORY_TILES: Array<{ label: string; value: string; Icon: any }> = [
  { label: 'Music',        value: 'Music',         Icon: Music },
  { label: 'Food & Drink', value: 'Food & Drink',  Icon: UtensilsCrossed },
  { label: 'Arts & Theater', value: 'Arts & Theater', Icon: Drama },
  { label: 'Outdoors',     value: 'Outdoors',      Icon: Trees },
  { label: 'Sports',       value: 'Sports',        Icon: Trophy },
  { label: 'Family',       value: 'Family & Kids', Icon: Users },
]

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
    background: 'rgba(26,24,48,0.5)',
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

const V2_CAT_STYLE: Record<string, { color: string; grad: string }> = {
  'Music':            { color: '#7c5cff', grad: 'linear-gradient(135deg,#3a2a5e,#7c5cff)' },
  'Food & Drink':     { color: '#e0892a', grad: 'linear-gradient(135deg,#7a4a1e,#e0892a)' },
  'Arts & Theater':   { color: '#d6457a', grad: 'linear-gradient(135deg,#6e2440,#d6457a)' },
  'Outdoors':         { color: '#2fa36b', grad: 'linear-gradient(135deg,#1e5e44,#2fa36b)' },
  'Sports':           { color: '#2f7fa3', grad: 'linear-gradient(135deg,#1c4a60,#2f7fa3)' },
  'Running & Races':  { color: '#e0892a', grad: 'linear-gradient(135deg,#7a4a1e,#e0892a)' },
  'Family & Kids':    { color: '#c0489b', grad: 'linear-gradient(135deg,#62265a,#c0489b)' },
  'Wellness':         { color: '#3aa39a', grad: 'linear-gradient(135deg,#1f5e58,#3aa39a)' },
  'Education & Talks':{ color: '#5566c4', grad: 'linear-gradient(135deg,#2e3670,#5566c4)' },
  'Community':        { color: '#6b61d6', grad: 'linear-gradient(135deg,#393379,#6b61d6)' },
  'Nightlife':        { color: '#b8478f', grad: 'linear-gradient(135deg,#5e2349,#b8478f)' },
}
function v2CatStyleFor(ev: V2YocEvent) {
  const cats = [...(ev.filter_categories || []), ...(ev.categories || [])]
  for (const c of cats) { if (V2_CAT_STYLE[c]) return { bucket: c, ...V2_CAT_STYLE[c] } }
  return { bucket: 'Community', ...V2_CAT_STYLE['Community'] }
}

function V2FeaturedCard({ event, onClick, viewedDay }: { event: V2YocEvent; onClick: () => void; viewedDay?: string }) {
  const startStr = (event.date || '').slice(0, 10)
  const endStr = (event.end_date || startStr).slice(0, 10)
  const badgeStr = (viewedDay && startStr <= viewedDay && viewedDay <= endStr) ? viewedDay : startStr
  const date = v2ParseEventDate(badgeStr)
  const MON = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
  const dow = date ? ['SUN','MON','TUE','WED','THU','FRI','SAT'][date.getDay()] : '?'
  const mon = date ? MON[date.getMonth()] : ''
  const dnum = date ? date.getDate() : ''
  const time = v2FormatTimeDisplay(event.start_time)
  const st = v2CatStyleFor(event)
  const hasImg = !!event.image_url && /^https?:\/\//.test(event.image_url)
  const isFree = event.is_free === true
  const priceTag = isFree ? 'Free' : (event.price && event.price.trim() ? event.price : null)
  const desc = (event.description || '').trim()
  const shortDesc = desc.length > 120 ? desc.slice(0, 120).replace(/\s+\S*$/, '') + '\u2026' : desc

  return (
    <button onClick={onClick} style={{
      display: 'flex', flexDirection: 'column', textAlign: 'left', width: '100%',
      background: 'rgba(255,255,255,0.06)', border: '2px solid #e0a83a', borderRadius: 16, overflow: 'hidden',
      cursor: 'pointer', padding: 0, fontFamily: "'DM Sans', sans-serif",
      boxShadow: 'none',
    }}>
      {hasImg && (
        <div style={{ aspectRatio: '3 / 2', position: 'relative',
          background: `center/cover no-repeat url(${event.image_url})` }} />
      )}
      <div style={{ padding: '12px 14px 14px', display: 'flex', flexDirection: 'column', flex: 1 }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: '#b9aef5' }}>{dow}{(time.hour || time.period) ? ' \u00b7 ' : ''}{time.hour}{time.period ? ' ' + time.period : ''}</div>
          <h3 style={{ fontSize: 13, fontWeight: 700, lineHeight: 1.25, margin: '2px 0 3px', color: '#fff',
            display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>{event.title}</h3>
          {event.location && <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.6)', fontWeight: 500,
            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{event.location}</div>}
          {priceTag && <div style={{ fontSize: 11, fontWeight: 700, color: isFree ? '#4ade80' : '#c4b5fd', marginTop: 3 }}>{priceTag}</div>}
          <span style={{
            display: 'inline-block', fontSize: 10, fontWeight: 700, letterSpacing: 0.2,
            color: st.color, background: st.color + '22',
            padding: '2px 8px', borderRadius: 999, marginTop: 5, width: 'fit-content',
          }}>{st.bucket}</span>
        </div>
      </div>
    </button>
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
  const cat = v2CatStyleFor(event)
  const hasImg = !!event.image_url && /^https?:\/\//.test(event.image_url)
  return (
    <button
      onClick={onClick}
      style={{
        width: '100%', textAlign: 'left',
        background: 'rgba(255,255,255,0.06)',
        border: '1px solid rgba(255,255,255,0.12)',
        boxShadow: 'none',
        borderRadius: 12, padding: 8,
        display: 'flex', gap: 10, alignItems: 'stretch',
        marginBottom: 0, cursor: 'pointer',
        fontFamily: "'DM Sans', sans-serif",
        transition: 'all 0.15s ease',
        color: 'inherit', font: 'inherit', WebkitAppearance: 'none',
      }}
      onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(255,255,255,0.10)' }}
      onMouseLeave={(e) => { e.currentTarget.style.background = 'rgba(255,255,255,0.06)' }}
    >
      {/* Left: photo, or category-gradient fallback when no image */}
      <div style={{
        flexShrink: 0, width: 76, alignSelf: 'stretch', minHeight: 76,
        borderRadius: 8, overflow: 'hidden',
        background: hasImg ? `center/cover no-repeat url(${event.image_url})` : cat.grad,
      }} />
      {/* Right: time / title / venue */}
      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
        {event.start_time && !event._time_uncertain && (
          <div style={{ fontSize: 11, fontWeight: 700, color: '#b9aef5', marginBottom: 1 }}>
            {time.hour}{time.period ? ' ' + time.period.toLowerCase() : ''}
          </div>
        )}
        <div style={{
          fontWeight: 700, fontSize: 14, color: '#fff', lineHeight: 1.25, marginBottom: 2,
          display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden',
        }}>
          {event.title}
        </div>
        {(event.venue_name || event.location) && (
          <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.6)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {event.venue_name || event.location}
            {event.price && <span style={{ color: (event.price || '').toLowerCase() === 'free' ? '#4ade80' : '#c4b5fd', marginLeft: 8, fontWeight: 600 }}>· {event.price}</span>}
            {event.is_free === true && !event.price && <span style={{ color: '#4ade80', marginLeft: 8, fontWeight: 600 }}>· Free</span>}
          </div>
        )}
        <span style={{
          display: 'inline-block', fontSize: 10, fontWeight: 700, letterSpacing: 0.2,
          color: cat.color, background: cat.color + '22',
          padding: '2px 8px', borderRadius: 999, marginTop: 5, width: 'fit-content',
        }}>{cat.bucket}</span>
      </div>
    </button>
  )
}

type FilterOption = { value: string; label: string }

function FilterDropdown({
  label, value, options, onChange, minWidth = 150,
}: {
  label: string
  value: string
  options: FilterOption[]
  onChange: (v: string) => void
  minWidth?: number
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement | null>(null)
  useEffect(() => {
    if (!open) return
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [open])
  return (
    <div ref={ref} style={{ position: 'relative', display: 'inline-block' }}>
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        style={{
          display: 'inline-flex', alignItems: 'center', gap: 6,
          justifyContent: 'space-between',
          padding: '7px 14px', fontSize: 13, fontWeight: 600,
          minWidth, boxSizing: 'border-box',
          borderRadius: 999, cursor: 'pointer',
          background: 'rgba(26,24,48,0.5)',
          border: '1px solid rgba(255,255,255,0.18)',
          color: '#fff', fontFamily: 'inherit', whiteSpace: 'nowrap',
        }}
      >
        {label}
        <span style={{ fontSize: 10, opacity: 0.7, transform: open ? 'rotate(180deg)' : 'none', transition: 'transform 0.15s' }}>▾</span>
      </button>
      {open && (
        <div style={{
          position: 'absolute', top: 'calc(100% + 6px)', left: 0, zIndex: 200,
          background: '#211a45', border: '1px solid rgba(175,169,236,0.28)',
          borderRadius: 12, padding: 5, minWidth: 180,
          boxShadow: '0 16px 40px rgba(0,0,0,0.5)',
        }}>
          {options.map(opt => (
            <button
              key={opt.value}
              type="button"
              onClick={() => { onChange(opt.value); setOpen(false) }}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                width: '100%', textAlign: 'left', gap: 10,
                padding: '8px 12px', fontSize: 13, borderRadius: 8,
                background: opt.value === value ? 'rgba(127,119,221,0.28)' : 'transparent',
                border: 'none', cursor: 'pointer', color: '#fff', fontFamily: 'inherit',
              }}
            >
              <span>{opt.label}</span>
              {opt.value === value && <span style={{ color: '#AFA9EC', fontSize: 13 }}>✓</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

function DateRangeDropdown({
  label, from, to, onFrom, onTo, onToday, onAllUpcoming,
  onTomorrow, onWeekend, onNext7, onFieldFocus, minWidth = 150,
}: {
  label: string
  from: string
  to: string
  onFrom: (v: string) => void
  onTo: (v: string) => void
  onToday: () => void
  onAllUpcoming: () => void
  onTomorrow?: () => void
  onWeekend?: () => void
  onNext7?: () => void
  onFieldFocus?: () => void
  minWidth?: number
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement | null>(null)
  useEffect(() => {
    if (!open) return
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [open])
  return (
    <div ref={ref} style={{ position: 'relative', display: 'inline-block' }}>
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        style={{
          display: 'inline-flex', alignItems: 'center', gap: 6,
          justifyContent: 'space-between',
          padding: '7px 14px', fontSize: 13, fontWeight: 600,
          minWidth, boxSizing: 'border-box',
          borderRadius: 999, cursor: 'pointer',
          background: 'rgba(26,24,48,0.5)',
          border: '1px solid rgba(255,255,255,0.18)',
          color: '#fff', fontFamily: 'inherit', whiteSpace: 'nowrap',
        }}
      >
        {label}
        <span style={{ fontSize: 10, opacity: 0.7, transform: open ? 'rotate(180deg)' : 'none', transition: 'transform 0.15s' }}>▾</span>
      </button>
      {open && (
        <div style={{
          position: 'absolute', top: 'calc(100% + 6px)', left: 0, zIndex: 200,
          background: '#211a45', border: '1px solid rgba(175,169,236,0.28)',
          borderRadius: 12, padding: 12, minWidth: 210,
          boxShadow: '0 16px 40px rgba(0,0,0,0.5)',
        }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 10 }}>
            <button type="button" onClick={() => { onToday(); setOpen(false) }}
              style={{ padding: '6px 10px', fontSize: 12, fontWeight: 600, borderRadius: 8, border: '1px solid rgba(255,255,255,0.18)', background: 'transparent', color: '#fff', cursor: 'pointer', fontFamily: 'inherit' }}>Today</button>
            {onTomorrow && (
              <button type="button" onClick={() => { onTomorrow(); setOpen(false) }}
                style={{ padding: '6px 10px', fontSize: 12, fontWeight: 600, borderRadius: 8, border: '1px solid rgba(255,255,255,0.18)', background: 'transparent', color: '#fff', cursor: 'pointer', fontFamily: 'inherit' }}>Tomorrow</button>
            )}
            {onWeekend && (
              <button type="button" onClick={() => { onWeekend(); setOpen(false) }}
                style={{ padding: '6px 10px', fontSize: 12, fontWeight: 600, borderRadius: 8, border: '1px solid rgba(255,255,255,0.18)', background: 'transparent', color: '#fff', cursor: 'pointer', fontFamily: 'inherit' }}>This weekend</button>
            )}
            {onNext7 && (
              <button type="button" onClick={() => { onNext7(); setOpen(false) }}
                style={{ padding: '6px 10px', fontSize: 12, fontWeight: 600, borderRadius: 8, border: '1px solid rgba(255,255,255,0.18)', background: 'transparent', color: '#fff', cursor: 'pointer', fontFamily: 'inherit' }}>Next 7 days</button>
            )}
            <button type="button" onClick={() => { onAllUpcoming(); setOpen(false) }}
              style={{ padding: '6px 10px', fontSize: 12, fontWeight: 600, borderRadius: 8, border: '1px solid rgba(255,255,255,0.18)', background: 'transparent', color: '#fff', cursor: 'pointer', fontFamily: 'inherit' }}>All upcoming</button>
          </div>
          <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.45)', textTransform: 'uppercase', letterSpacing: 0.4, marginBottom: 6 }}>Or a date range</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.55)', textTransform: 'uppercase', letterSpacing: 0.4 }}>From</span>
              <input type="date" value={from} onFocus={() => onFieldFocus?.()} onChange={(e) => { if (e.target.value) onFrom(e.target.value) }}
                style={{ padding: '7px 10px', fontSize: 13, borderRadius: 8, border: '1px solid rgba(255,255,255,0.18)', background: 'rgba(26,24,48,0.5)', color: '#fff', colorScheme: 'dark', fontFamily: 'inherit' }} />
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.55)', textTransform: 'uppercase', letterSpacing: 0.4 }}>To</span>
              <input type="date" value={to} min={from} onFocus={() => onFieldFocus?.()} onChange={(e) => onTo(e.target.value)}
                style={{ padding: '7px 10px', fontSize: 13, borderRadius: 8, border: '1px solid rgba(255,255,255,0.18)', background: 'rgba(26,24,48,0.5)', color: '#fff', colorScheme: 'dark', fontFamily: 'inherit' }} />
            </label>
          </div>
        </div>
      )}
    </div>
  )
}

function MultiFilterDropdown({
  label, selected, options, onToggle, onClear, minWidth = 150,
}: {
  label: string
  selected: Set<string>
  options: FilterOption[]
  onToggle: (v: string) => void
  onClear: () => void
  minWidth?: number
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement | null>(null)
  useEffect(() => {
    if (!open) return
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [open])
  const active = selected.size > 0
  return (
    <div ref={ref} style={{ position: 'relative', display: 'inline-block' }}>
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        style={{
          display: 'inline-flex', alignItems: 'center', gap: 6,
          justifyContent: 'space-between',
          padding: '7px 14px', fontSize: 13, fontWeight: 600,
          minWidth, boxSizing: 'border-box',
          borderRadius: 999, cursor: 'pointer',
          background: active ? 'rgba(127,119,221,0.28)' : 'rgba(26,24,48,0.5)',
          border: active ? '1px solid rgba(127,119,221,0.6)' : '1px solid rgba(255,255,255,0.18)',
          color: '#fff', fontFamily: 'inherit', whiteSpace: 'nowrap',
        }}
      >
        {label}
        <span style={{ fontSize: 10, opacity: 0.7, transform: open ? 'rotate(180deg)' : 'none', transition: 'transform 0.15s' }}>▾</span>
      </button>
      {open && (
        <div style={{
          position: 'absolute', top: 'calc(100% + 6px)', left: 0, zIndex: 200,
          background: '#211a45', border: '1px solid rgba(175,169,236,0.28)',
          borderRadius: 12, padding: 5, minWidth: 200, maxHeight: 320, overflowY: 'auto',
          boxShadow: '0 16px 40px rgba(0,0,0,0.5)',
        }}>
          <button
            type="button"
            onClick={() => { onClear(); }}
            style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              width: '100%', textAlign: 'left', gap: 10,
              padding: '8px 12px', fontSize: 13, borderRadius: 8,
              background: selected.size === 0 ? 'rgba(127,119,221,0.28)' : 'transparent',
              border: 'none', cursor: 'pointer', color: '#fff', fontFamily: 'inherit',
              marginBottom: 2,
            }}
          >
            <span>All categories</span>
            {selected.size === 0 && <span style={{ color: '#AFA9EC' }}>✓</span>}
          </button>
          {options.map(opt => {
            const on = selected.has(opt.value)
            return (
              <button
                key={opt.value}
                type="button"
                onClick={() => onToggle(opt.value)}
                style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  width: '100%', textAlign: 'left', gap: 10,
                  padding: '8px 12px', fontSize: 13, borderRadius: 8,
                  background: on ? 'rgba(127,119,221,0.28)' : 'transparent',
                  border: 'none', cursor: 'pointer', color: '#fff', fontFamily: 'inherit',
                }}
              >
                <span>{opt.label}</span>
                {on && <span style={{ color: '#AFA9EC' }}>✓</span>}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}

export function EventsV2Embedded({ cityKeyProp, initialEvents }: { cityKeyProp?: string; initialEvents?: V2YocEvent[] } = {}) {
  const cityLabel = ({ parkcity: 'Park City', heber: 'Heber Valley', jackson: 'Jackson Hole', elkhartlake: 'Elkhart Lake', greenlake: 'Green Lake' } as Record<string, string>)[cityKeyProp || 'parkcity'] || 'your area'
  // Per-city hero image (falls back to the generic /hero.webp). Fixes the hero
  // not matching the city — e.g. Green Lake was showing a Park City street scene.
  const heroImg = ({ greenlake: '/green-lake-hero.webp' } as Record<string, string>)[cityKeyProp || ''] || '/hero.webp'
  // Seed from server-provided events so the FIRST render (server-side) shows
  // real cards instead of a "Loading…" spinner — this is what paints the LCP
  // element fast. The client fetch below still runs to refresh + load other
  // cities, but the initial paint no longer waits on it.
  const [events, setEvents] = useState<V2YocEvent[]>(initialEvents || [])
  // Events from cities OTHER than the current one. Used by cross-city search
  // (Model C): current city's events surface first, fallback to nearest from
  // other cities when local results are sparse.
  const [otherCityEvents, setOtherCityEvents] = useState<V2YocEvent[]>([])
  // City filter for cross-city search. Defaults to the current city so the
  // overlay isn't overwhelming on open; user can tap "All" or another city
  // pill to expand.
  type CityFilterValue = 'current' | 'all' | 'parkcity' | 'heber' | 'jackson' | 'elkhartlake'
  const [cityFilter, setCityFilter] = useState<CityFilterValue>('current')
  const [loading, setLoading] = useState(!(initialEvents && initialEvents.length))
  const [dayFilter, setDayFilter] = useState<V2DayFilter>('today')
  const [timeFilter, setTimeFilter] = useState<V2TimeFilter>('any')
  const [activeCategories, setActiveCategories] = useState<Set<string>>(new Set())
  const [showAllCategories, setShowAllCategories] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedEvent, setSelectedEvent] = useState<EventModalData | null>(null)
  const [showResultsView, setShowResultsView] = useState(false)
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set())
  const [activeChips, setActiveChips] = useState<Set<ChipId>>(new Set())
  const [chipPickedDate, setChipPickedDate] = useState<string>('')
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const [showMoreFilters, setShowMoreFilters] = useState(false)
  // "Free" quick-pill filter. Off by default so it doesn't alter existing
  // behavior; when on, only free events pass (uses isFreeEvent).
  const [freeOnly, setFreeOnly] = useState(false)
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
  // Mount guard for client-only portals (e.g. the See-all overlay uses
  // createPortal -> document.body, which doesn't exist during SSR).
  const [mounted, setMounted] = useState(false)
  useEffect(() => { setMounted(true) }, [])
  // Track narrow viewports so the header can stack vertically on mobile
  // (the 3-column desktop layout crushes the title into 4 lines on a phone).
  const [isMobile, setIsMobile] = useState(false)
  useEffect(() => {
    const check = () => setIsMobile(window.innerWidth <= 640)
    check()
    window.addEventListener('resize', check)
    return () => window.removeEventListener('resize', check)
  }, [])

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
      // When the "See all" overlay is open, that portal is our UI rendered
      // outside the dropdown's DOM tree. Don't treat its clicks as "outside"
      // -- otherwise opening the overlay immediately wipes the search query
      // we used to populate it.
      if (showResultsView) return
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
        // Escape closes the overlay (if open) but preserves search state so
        // the user can re-open the dropdown without retyping.
        if (showResultsView) {
          setShowResultsView(false)
          return
        }
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
  }, [dropdownOpen, selectedEvent, showResultsView])


  const [pickedDate, setPickedDate] = useState<string>(v2DateToStr(v2TodayMountain()))
  // End of a custom date RANGE in 'pickdate' mode. Empty string = single day
  // (pickedDate only). When set (and >= pickedDate) events occurring anywhere in
  // [pickedDate, pickedEndDate] are shown.
  const [pickedEndDate, setPickedEndDate] = useState<string>('')
  // Effective end of the picked range: clamp to start when end is unset/invalid,
  // so a single-day pick keeps its current behavior.
  const pickedRangeEnd = (pickedEndDate && pickedEndDate >= pickedDate) ? pickedEndDate : pickedDate
  // Radius ALWAYS initializes to 25 so server and client render identically
  // (no hydration mismatch). The mount effect below reads the ?radius= URL
  // param and corrects the value right after hydration — that's what makes
  // radius survive refresh/share and stay drivable by the nav RadiusPicker.
  const [radius, setRadius] = useState<number>(25)
  // Set radius + sync the URL (no navigation/reload) + notify the nav pill.
  // Shared by the hero radius dropdown and the nav RadiusPicker so both stay
  // in lockstep regardless of which one the user touches.
  const applyRadius = (n: number) => {
    setRadius(n)
    if (typeof window !== 'undefined') {
      const u = new URL(window.location.href)
      u.searchParams.set('radius', String(n))
      window.history.replaceState(null, '', u.toString())
      window.dispatchEvent(new CustomEvent('yoocal:radius', { detail: n }))
    }
  }
  // Listen for radius changes fired by the nav RadiusPicker (separate
  // component, no shared parent) and sync local state. Also re-reads the URL
  // param on mount to settle any SSR/client hydration difference.
  useEffect(() => {
    const onRadius = (e: Event) => {
      const n = (e as CustomEvent).detail
      if ([5, 10, 25, 50].includes(n)) setRadius(n)
    }
    window.addEventListener('yoocal:radius', onRadius)
    const r = Number(new URLSearchParams(window.location.search).get('radius'))
    if ([5, 10, 25, 50].includes(r)) setRadius(r)
    return () => window.removeEventListener('yoocal:radius', onRadius)
  }, [])
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
      greenlake: '/events-greenlake.json',
    }
    const file = fileMap[cityKeyLocal] || '/events.json'
    setLoading(true)
    // Cross-city loading: fetch the current city's file + all other cities' files
    // in parallel. Other-city events power Model C "show nearby events" when
    // local matches are sparse.
    const otherFiles = Object.entries(fileMap)
      .filter(([k]) => k !== cityKeyLocal)
      .map(([k, f]) => ({ key: k, file: f }))
    // Render the CURRENT city as soon as ITS file arrives — do NOT block first
    // paint on the other cities' files (which total several MB and only power
    // the sparse-results cross-city fallback). Other cities load in the
    // background and merge in when ready.
    fetch(file)
      .then(r => r.json())
      .then((mainData: { events?: V2YocEvent[] } | V2YocEvent[]) => {
        setEvents(((mainData as { events?: V2YocEvent[] }).events || mainData) as V2YocEvent[])
        setLoading(false)  // current city is enough to render; unblock paint
      })
      .catch(e => {
        console.error('V2: failed to load current-city events', e)
        setLoading(false)
      })
    // Background: other-city events for the cross-city fallback. Not on the
    // critical path; failures are silent and just disable the fallback.
    Promise.all(
      otherFiles.map(({ key, file: f }) =>
        fetch(f).then(r => r.json()).then(d => ({ key, events: (d.events || d) as V2YocEvent[] })).catch(() => ({ key, events: [] as V2YocEvent[] }))
      )
    ).then((otherResults) => {
      const others: V2YocEvent[] = []
      for (const { key, events: cityEvents } of otherResults) {
        for (const ev of cityEvents) {
          others.push({ ...ev, _sourceCity: key } as V2YocEvent)
        }
      }
      setOtherCityEvents(others)
    }).catch(() => { /* fallback disabled if other cities fail to load */ })
  }, [cityKeyProp])

  // A fresh visit to a city should open on what's happening now, not all
  // upcoming. Reset to "today" whenever the embedded calendar loads a city.
  useEffect(() => {
    setDayFilter('today')
    setSearchQuery('')
  }, [cityKeyProp])

  const filteredEvents = useMemo(() => {
    let result = events
    const today = v2TodayMountain()
    const todayStr = v2DateToStr(today)

    // An event "occurs on" a day if that day falls between its start date and
    // end_date (inclusive). Multi-day events (festivals like Song Summit) should
    // appear on every day they run, not just the first day.

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
      // Range-aware: occursInRange with start === end is equivalent to occursOn,
      // so a single-day pick (pickedRangeEnd === pickedDate) behaves as before.
      result = result.filter(e => occursInRange(e, pickedDate, pickedRangeEnd))
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
    
    if (activeCategories.size > 0) {
      result = result.filter(e => ((e.filter_categories && e.filter_categories.length ? e.filter_categories : (e.categories || [])).some(c => activeCategories.has(c))))
    }

    if (freeOnly) result = result.filter(e => isFreeEvent(e))


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
  }, [events, dayFilter, timeFilter, activeCategories, freeOnly, pickedDate, pickedRangeEnd, radius, userCoords, cityKey])

  // Group the filtered events by occurrence day for RANGE views (weekend / 7days
  // / all / a multi-day picked range). Returns null for single-day modes (today
  // / tomorrow / single-date pick), where the flat list is rendered as before.
  // A multi-day or recurring event appears under EACH day it occurs, so the
  // weekend reads as an itinerary (Fri, then Sat, then Sun) rather than dups.
  const groupedByDay = useMemo(() => {
    const isRange =
      dayFilter === 'weekend' || dayFilter === '7days' || dayFilter === 'all' ||
      (dayFilter === 'pickdate' && pickedDate !== pickedRangeEnd)
    if (!isRange) return null
    if (filteredEvents.length === 0) return null

    // Distinct occurrence days actually present among the filtered events.
    const dayset = new Set<string>()
    for (const e of filteredEvents) {
      const s = (e.date || '').slice(0, 10)
      const en = (e.end_date || s).slice(0, 10)
      if (!s) continue
      // walk s..en (cap at 14 days to avoid pathological ranges)
      let cur = s, guard = 0
      while (cur <= en && guard < 14) {
        dayset.add(cur)
        const [y, m, d] = cur.split('-').map(Number)
        const nx = new Date(y, m - 1, d + 1)
        cur = `${nx.getFullYear()}-${String(nx.getMonth()+1).padStart(2,'0')}-${String(nx.getDate()).padStart(2,'0')}`
        guard++
      }
    }
    const days = Array.from(dayset).sort()

    const DOWF = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday']
    const MONF = ['January','February','March','April','May','June','July','August','September','October','November','December']
    const timeMin = (e: V2YocEvent) => {
      const t = v2ParseTime12h(e.start_time)
      return t === null ? 24 * 60 + 1 : t
    }
    return days.map(dateStr => {
      const [y, m, d] = dateStr.split('-').map(Number)
      const dt = new Date(y, m - 1, d)
      const label = `${DOWF[dt.getDay()]}, ${MONF[dt.getMonth()]} ${dt.getDate()}`
      const evs = filteredEvents
        .filter(e => occursOn(e, dateStr))
        .sort((a, b) => timeMin(a) - timeMin(b))
      return { dateStr, label, events: evs }
    }).filter(g => g.events.length > 0)
  }, [filteredEvents, dayFilter, pickedDate, pickedRangeEnd])

  // Empty-day fall-forward: if the chosen window has nothing matching, find the
  // soonest FUTURE day (after the window) whose events still pass the other
  // active filters, so a quiet day points the user forward instead of dead-ending.
  const fallForwardEvents = useMemo(() => {
    if (loading) return null
    if (filteredEvents.length > 0) return null
    if (dayFilter === 'all') return null
    const today = v2TodayMountain()
    const todayStr = v2DateToStr(today)
    let refEnd = todayStr
    let emptyLabel = 'Nothing today'
    if (dayFilter === 'tomorrow') {
      const t = new Date(today); t.setDate(today.getDate() + 1); refEnd = v2DateToStr(t); emptyLabel = 'Nothing tomorrow'
    } else if (dayFilter === 'weekend') {
      const { end } = v2WeekendDates(); refEnd = v2DateToStr(end); emptyLabel = 'Nothing this weekend'
    } else if (dayFilter === '7days') {
      const w = new Date(today); w.setDate(today.getDate() + 7); refEnd = v2DateToStr(w); emptyLabel = 'Nothing in the next 7 days'
    } else if (dayFilter === 'pickdate') {
      refEnd = pickedRangeEnd; emptyLabel = pickedRangeEnd > pickedDate ? 'Nothing in that range' : 'Nothing on that day'
    }
    let pool = events
      .filter(e => ((e.end_date || e.date) || '') >= todayStr)
      .filter(e => (e.date || '').slice(0, 10) > refEnd)
    if (timeFilter !== 'any') {
      pool = pool.filter(e => {
        const t = v2ParseTime12h(e.start_time)
        if (t === null) return true
        if (timeFilter === 'morning') return t < 12 * 60
        if (timeFilter === 'afternoon') return t >= 12 * 60 && t < 17 * 60
        if (timeFilter === 'evening') return t >= 17 * 60 && t < 21 * 60
        if (timeFilter === 'latenight') return t >= 21 * 60
        return true
      })
    }
    if (activeCategories.size > 0) {
      pool = pool.filter(e => ((e.filter_categories && e.filter_categories.length ? e.filter_categories : (e.categories || [])).some(c => activeCategories.has(c))))
    }
    if (freeOnly) pool = pool.filter(e => isFreeEvent(e))
    const origin = userCoords || CITY_CENTERS[cityKey] || CITY_CENTERS.parkcity
    if (origin) {
      pool = pool.filter(e => {
        if (typeof e.lat !== 'number' || typeof e.lng !== 'number') return true
        return v2DistanceMiles(origin.lat, origin.lng, e.lat, e.lng) <= radius
      })
    }
    if (pool.length === 0) return null
    pool.sort((a, b) => {
      if (a.date !== b.date) return (a.date || '').localeCompare(b.date || '')
      const ta = v2ParseTime12h(a.start_time) ?? 24 * 60
      const tb = v2ParseTime12h(b.start_time) ?? 24 * 60
      return ta - tb
    })
    const nextDay = (pool[0].date || '').slice(0, 10)
    const dayEvents = pool.filter(e => (e.date || '').slice(0, 10) === nextDay)
    const pretty = new Date(nextDay + 'T12:00:00').toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })
    return { date: nextDay, events: dayEvents, emptyLabel, pretty }
  }, [loading, filteredEvents, events, dayFilter, timeFilter, activeCategories, freeOnly, pickedDate, pickedRangeEnd, radius, userCoords, cityKey])

  const allUpcomingMatches = useMemo(() => {
    const q = searchQuery.trim().toLowerCase()
    const todayStr = v2DateToStr(v2TodayMountain())
    if (!q && dayFilter === 'all' && timeFilter === 'any' && activeCategories.size === 0) return []
    // Relevance score for ordering: a title hit on the query beats a mere
    // description/category/synonym hit, so searching "miners day" surfaces the
    // actual "Miners Day Parade" above loosely-matching June lectures. Matches
    // the tiering used by the "see all" overlay so both views agree.
    const _qTokens = _searchNormalize(q).split(/\s+/).filter(Boolean)
    const _relevance = (e: V2YocEvent): number => {
      if (_qTokens.length === 0) return 0
      const title = _searchNormalize(e.title || '')
      if (_qTokens.every(t => title.includes(t))) return 1       // all query words in title -> soonest-first within this tier
      if (_qTokens.some(t => title.includes(t))) return 2        // some tokens in title
      return 3                                                    // matched elsewhere
    }
    const filterAndSort = (list: V2YocEvent[]) => list
      .filter(e => ((e.end_date || e.date) || '') >= todayStr)
      .filter(e => matchesQuery(e, q))
      .filter(e => {
        // When filter (shared semantics with main view). 'all'/unknown = no
        // date narrowing, so a search shows ALL upcoming matches by default.
        if (dayFilter === 'today') { if (!occursOn(e, todayStr)) return false }
        else if (dayFilter === 'tomorrow') {
          const tom = new Date(v2TodayMountain()); tom.setDate(tom.getDate() + 1)
          if (!occursOn(e, v2DateToStr(tom))) return false
        } else if (dayFilter === 'weekend') {
          const { start, end } = v2WeekendDates()
          if (!occursInRange(e, v2DateToStr(start), v2DateToStr(end))) return false
        } else if (dayFilter === '7days') {
          const week = new Date(v2TodayMountain()); week.setDate(week.getDate() + 7)
          if (!occursInRange(e, todayStr, v2DateToStr(week))) return false
        } else if (dayFilter === 'pickdate') {
          if (!occursInRange(e, pickedDate, pickedRangeEnd)) return false
        }
        // Time filter (shared with main view).
        if (timeFilter !== 'any') {
          const t = v2ParseTime12h(e.start_time)
          if (t !== null) {
            if (timeFilter === 'morning' && !(t < 12*60)) return false
            if (timeFilter === 'afternoon' && !(t >= 12*60 && t < 17*60)) return false
            if (timeFilter === 'evening' && !(t >= 17*60 && t < 21*60)) return false
            if (timeFilter === 'latenight' && !(t >= 21*60)) return false
          }
        }
        // Vibe filter (multi-select; empty = all).
        if (activeCategories.size > 0) {
          if (!((e.filter_categories && e.filter_categories.length ? e.filter_categories : (e.categories || [])).some(c => activeCategories.has(c)))) return false
        }
        // Free quick-pill filter (shared with main view).
        if (freeOnly && !isFreeEvent(e)) return false
        return true
      })
      .sort((a, b) => {
        const ra = _relevance(a), rb = _relevance(b)
        if (ra !== rb) return ra - rb                            // relevance first
        return (a.date || '').localeCompare(b.date || '')        // then by date
      })
    // Cross-city search: current city's matches surface first (most relevant
    // to the user who picked this city), then other-city matches appended.
    // Piece 3 will add distance-based sorting within the other-city tier;
    // for now they appear in chronological order, segregated from local.
    const local = filterAndSort(events)
    const other = filterAndSort(otherCityEvents)
    // Apply city filter: 'current' (default) shows only local results — same
    // experience users had before cross-city. 'all' returns local first then
    // other-city. Specific city pill returns only that city's results.
    const cityKeyLocal = cityKeyProp || 'parkcity'
    // Nearby-city fallback: if the current city has NO matches for an active
    // search, surface results from geographically adjacent cities (Park City
    // <-> Heber are ~20min apart; Jackson and Elkhart stand alone). Results
    // keep their _sourceCity badge so the user sees they're in another town.
    const NEARBY_CITIES: Record<string, string[]> = {
      parkcity: ['heber'],
      heber: ['parkcity'],
      jackson: [],
      elkhartlake: [],
    }
    if (cityFilter === 'current') {
      if (local.length === 0 && q) {
        const nearby = NEARBY_CITIES[cityKeyLocal] || []
        return other
          .filter(e => nearby.includes(e._sourceCity || ''))
          .sort((a, b) => (a.date || '').localeCompare(b.date || ''))
      }
      return local
    }
    if (cityFilter === 'all') {
      // Sort by distance from the current city's center, then by date.
      // Current-city events get distance 0 so they always appear first;
      // other cities sort by how close they are to where the user is browsing.
      const originCenter = CITY_CENTERS[cityKeyLocal] || CITY_CENTERS.parkcity
      const cityDistance = (cityKey: string): number => {
        if (!cityKey || cityKey === cityKeyLocal) return 0
        const c = CITY_CENTERS[cityKey]
        if (!c || !originCenter) return Infinity
        return v2DistanceMiles(originCenter.lat, originCenter.lng, c.lat, c.lng)
      }
      const combined = [...local, ...other]
      combined.sort((a, b) => {
        const ad = cityDistance(a._sourceCity || cityKeyLocal)
        const bd = cityDistance(b._sourceCity || cityKeyLocal)
        if (ad !== bd) return ad - bd
        return (a.date || '').localeCompare(b.date || '')
      })
      return combined
    }
    // Specific city: filter from the appropriate pool
    if (cityFilter === cityKeyLocal) return local
    return other.filter(e => (e._sourceCity || '') === cityFilter)
  }, [events, otherCityEvents, searchQuery, dayFilter, timeFilter, activeCategories, freeOnly, pickedDate, pickedRangeEnd, cityFilter, cityKeyProp])

  // Group results by normalized title for the "See all" overlay. Each row
  // shows one card per unique event identity, with all future occurrences
  // accessible by expanding. Smart sort within the result list:
  // 1) title starts with query (e.g. "park city trail series" -> all races)
  // 2) title contains all query tokens
  // 3) match was elsewhere (description / venue / category)
  // Chronological by next occurrence within each tier.
  const groupedResults = useMemo(() => {
    const q = searchQuery.trim().toLowerCase()
    const tokens = q.split(/\s+/).filter(Boolean)
    const groups = new Map<string, { key: string; occurrences: V2YocEvent[]; tier: number }>()
    const normalizeTitle = (t: string) => (t || '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim()
    for (const ev of allUpcomingMatches) {
      const key = normalizeTitle(ev.title) || 'untitled'
      const existing = groups.get(key)
      if (existing) {
        existing.occurrences.push(ev)
      } else {
        // Determine tier for sort
        const titleLower = (ev.title || '').toLowerCase()
        let tier = 2
        if (tokens.length > 0) {
          if (titleLower.startsWith(q)) tier = 0
          else if (tokens.every(t => titleLower.includes(t))) tier = 1
        } else {
          tier = 1  // no query, all entries equal
        }
        groups.set(key, { key, occurrences: [ev], tier })
      }
    }
    const arr = Array.from(groups.values())
    // Sort each group's occurrences chronologically
    for (const g of arr) {
      g.occurrences.sort((a, b) => (a.date || '').localeCompare(b.date || ''))
    }
    // Sort groups: tier first, then (when "All cities" is active) by
    // distance from the current city, then by next occurrence date.
    // Tier wins so prefix-match groups lead regardless of city; within a tier
    // closer cities come before farther ones; within a city date ascends.
    const cityKeyLocal = cityKeyProp || 'parkcity'
    const originCenter = CITY_CENTERS[cityKeyLocal] || CITY_CENTERS.parkcity
    const groupCityDist = (g: { occurrences: V2YocEvent[] }): number => {
      const sc = g.occurrences[0]?._sourceCity || cityKeyLocal
      if (sc === cityKeyLocal) return 0
      const c = CITY_CENTERS[sc]
      if (!c || !originCenter) return Infinity
      return v2DistanceMiles(originCenter.lat, originCenter.lng, c.lat, c.lng)
    }
    arr.sort((a, b) => {
      // Text search prioritizes RELEVANCE over proximity. If you typed words
      // that appear in an event's TITLE (tier 0 = title prefix, tier 1 = all
      // tokens in title), that event leads regardless of city — typing "princ"
      // surfaces "Princess and Pirate Train" even from a neighboring city.
      // Only weaker matches (tier 2: description / venue / category) stay
      // local-first by distance when "All cities" is active.
      const aTitle = a.tier <= 1
      const bTitle = b.tier <= 1
      if (aTitle !== bTitle) return aTitle ? -1 : 1
      if (aTitle && bTitle) {
        // Both match in the title: fall through to the soonest-date sort below
        // so a near-term occurrence isn't buried under a later exact-phrase match.
      } else if (cityFilter === 'all') {
        // Both are weaker matches: closer city leads.
        const adist = groupCityDist(a)
        const bdist = groupCityDist(b)
        if (adist !== bdist) return adist - bdist
      }
      const ad = a.occurrences[0]?.date || ''
      const bd = b.occurrences[0]?.date || ''
      return ad.localeCompare(bd)
    })
    return arr
  }, [allUpcomingMatches, searchQuery, cityFilter, cityKeyProp])
  
  // Featured events: things happening TODAY only. Manual flags first, then
  // today's best events ranked by tag richness. Empty if nothing today.
  const featuredEvents = useMemo(() => {
    // Featured highlights the best events in the CURRENTLY-VIEWED window — the
    // same date range the main list shows — not a hardcoded "today". Range
    // modes (weekend / 7days / all / a picked date range) span the whole
    // window; single-day modes are just that day.
    const today = v2TodayMountain()
    const todayStr = v2DateToStr(today)
    let rangeStart = todayStr
    let rangeEnd = todayStr
    if (dayFilter === 'tomorrow') {
      const tom = new Date(today); tom.setDate(today.getDate() + 1)
      rangeStart = rangeEnd = v2DateToStr(tom)
    } else if (dayFilter === 'weekend') {
      const { start, end } = v2WeekendDates()
      rangeStart = v2DateToStr(start); rangeEnd = v2DateToStr(end)
    } else if (dayFilter === '7days') {
      const week = new Date(today); week.setDate(today.getDate() + 7)
      rangeStart = todayStr; rangeEnd = v2DateToStr(week)
    } else if (dayFilter === 'pickdate') {
      rangeStart = pickedDate; rangeEnd = pickedRangeEnd
    } else if (dayFilter === 'all') {
      rangeStart = todayStr; rangeEnd = '9999-12-31'
    }
    // dayFilter === 'today' keeps rangeStart = rangeEnd = todayStr.

    const richness = (e: any) => ((e.filter_categories?.length || e.categories?.length || 0)) + (e.hook ? 2 : 0)
    const QUALITY_BAR = ({ parkcity: 2, jackson: 2, heber: 1, elkhartlake: 1, greenlake: 1 } as Record<string, number>)[cityKey] ?? 2  // multiple categories, or a hook — a genuine standout

    // Green Lake: chamber/VGL events almost never carry images, so the
    // image-gated logic below yields an empty strip. Instead feature ONE genuine
    // VGL public event per day, rotated deterministically by day-of-year (stable
    // within a day, rotates daily). Excludes non-public noise (recovery meetings,
    // support groups, board/committee meetings). No image required — the card's
    // category-gradient fallback handles display.
    if (cityKey === 'greenlake') {
      const NOISE = /\b(AA and|Al-Anon|support group|board meeting|committee|caregiver|staff meeting|book club|narcotics anonymous|overeaters|grief|CPR|first aid|blood drive|class|workshop|training|meeting|orientation|tutoring|office hours)\b/i
      const pool = events
        .filter((e: any) => occursInRange(e, rangeStart, rangeEnd))
        .filter((e: any) => /chamber\.visitgreenlake\.com/.test(e.link || ''))
        .filter((e: any) => typeof e._distance_mi !== 'number' || e._distance_mi <= 10)
        .filter((e: any) => !NOISE.test(e.title || ''))
        .sort((a: any, b: any) => (a.title || '').localeCompare(b.title || ''))
      if (!pool.length) return []
      const _start = new Date(today.getFullYear(), 0, 0)
      const _doy = Math.floor((today.getTime() - _start.getTime()) / 86400000)
      return [pool[_doy % pool.length]]
    }

    const FEATURED_RADIUS = 10
    const windowEvents = events.filter((e: any) =>
      occursInRange(e, rangeStart, rangeEnd)
      && !!e.image_url && /^https?:\/\//.test(e.image_url)
      && (typeof e._distance_mi !== 'number' || e._distance_mi <= FEATURED_RADIUS))

    // WEEKEND: feature up to 2 events PER DAY (Fri, Sat, Sun) = up to 6 total,
    // deduped by title across the whole weekend (a Fri+Sat event is used once,
    // on its earliest day). Other modes fall through to the generic logic below.
    if (dayFilter === 'weekend') {
      const { start } = v2WeekendDates()
      const dayList: string[] = []
      for (let i = 0; i < 3; i++) {
        const dd = new Date(start); dd.setDate(start.getDate() + i)
        dayList.push(v2DateToStr(dd))
      }
      const rich = (e: any) => ((e.filter_categories?.length || e.categories?.length || 0)) + (e.hook ? 2 : 0)
      const rankDay = (arr: any[]) => arr.slice().sort((a, b) =>
        (b.featured === true ? 1 : 0) - (a.featured === true ? 1 : 0) ||
        rich(b) - rich(a) ||
        (a.start_time || '').localeCompare(b.start_time || ''))
      const usedTitles = new Set<string>()
      const picks: any[] = []
      for (const day of dayList) {
        const onDay = rankDay(windowEvents.filter((e: any) => occursOn(e, day)))
        let added = 0
        for (const e of onDay) {
          if (added >= 2) break
          const key = (e.title || '').trim().toLowerCase()
          if (key && usedTitles.has(key)) continue
          if (key) usedTitles.add(key)
          picks.push({ ...e, _featuredDay: day })
          added++
        }
      }
      return picks
    }

    // Cap scales with how busy the window is: a quiet day shouldn't fill the
    // strip, a packed window can show more. This is a MAXIMUM — we still only
    // show genuine standouts up to it (never pad with filler).
    // Dedupe by title so a multi-day / multi-session event (e.g. a festival
    // running Fri+Sat) shows only ONE featured card. Sort earliest-first,
    // then keep the first occurrence per normalized title.
    const _seenTitles = new Set<string>()
    const _byDate = (e: any) => (e.date || '').slice(0, 10)
    const windowEventsDeduped = [...windowEvents]
      .sort((a, b) => _byDate(a).localeCompare(_byDate(b)) || (a.start_time || '').localeCompare(b.start_time || ''))
      .filter((e: any) => {
        const key = (e.title || '').trim().toLowerCase()
        if (!key) return true
        if (_seenTitles.has(key)) return false
        _seenTitles.add(key)
        return true
      })
    const n = windowEventsDeduped.length
    const MAX = n >= 11 ? 5 : n >= 5 ? 3 : 1

    // Manually-flagged events always lead (still capped by the tier).
    const manual = windowEventsDeduped.filter((e: any) => e.featured === true)
    if (manual.length >= MAX) return manual.slice(0, MAX)

    // Fill remaining slots with the window's genuine standouts: richest first,
    // soonest on ties (don't pad to MAX).
    const dstr = (e: any) => (e.date || '').slice(0, 10)
    const ranked = windowEventsDeduped
      .filter((e: any) => e.featured !== true)
      .sort((a, b) =>
        richness(b) - richness(a) ||
        dstr(a).localeCompare(dstr(b)) ||
        (a.start_time || '').localeCompare(b.start_time || ''))
    const standouts = ranked.filter((e: any) => richness(e) >= QUALITY_BAR)

    const combined = [...manual, ...standouts].slice(0, MAX)

    // Never show an empty strip when the window has events: fall back to the
    // single best event in the window.
    if (combined.length === 0 && ranked.length > 0) return ranked.slice(0, 1)
    return combined
  }, [events, dayFilter, pickedDate, pickedRangeEnd])
  
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
      const toDate = (s: string) => {
        const p = s.split('-')
        return p.length === 3 ? new Date(Number(p[0]), Number(p[1]) - 1, Number(p[2])) : null
      }
      const startD = toDate(pickedDate)
      // Show a range ("Jun 5 – Jun 12") when an end date past the start is set.
      if (pickedRangeEnd !== pickedDate) {
        const endD = toDate(pickedRangeEnd)
        if (startD && endD) return `${fmtShort(startD)} – ${fmtShort(endD)}`
      }
      return startD ? fmt(startD) : pickedDate
    }
    return 'All upcoming'
  }, [dayFilter, pickedDate, pickedRangeEnd])
  
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
    setPickedEndDate('')  // arrow navigation is single-day; drop any range end
    setDayFilter('pickdate')
  }
  
  const handleEventClick = (ev: V2YocEvent) => {
    setSelectedEvent({
      title: ev.title, date: ev.date, end_date: ev.end_date,
      start_time: ev.start_time, end_time: ev.end_time,
      location: ev.venue_name || ev.location,
      description: ev.description, link: ev.link, source: ev.source,
      is_free: ev.is_free, price: ev.price, categories: (ev.filter_categories && ev.filter_categories.length ? ev.filter_categories : ev.categories),
      image_url: ev.image_url,
    })
  }
  
  return (
    <div style={{ fontFamily: "'DM Sans', sans-serif" }}>
      {/* Photo hero: festival bg + dark overlay, holds title + search + filters */}
      <div style={{
        // overflow must stay visible: the search-results dropdown is positioned
        // inside this hero and would be clipped at the hero's bottom edge by
        // overflow:hidden, cutting off a tall results list.
        position: 'relative', overflow: 'visible',
        margin: 0, padding: '96px 28px 8px',
        marginLeft: 'calc(50% - 50vw)', marginRight: 'calc(50% - 50vw)', width: '100vw',
        borderRadius: '20px 20px 0 0',
        background: `linear-gradient(180deg, rgba(26,24,48,0.35), rgba(26,24,48,0.62)), url('${heroImg}') center/cover no-repeat`,
      }}>
        <div style={{ textAlign: 'center', marginBottom: 22 }}>
          <div role="presentation" style={{ fontFamily: "'DM Serif Display', serif", fontSize: 'clamp(44px, 6vw, 76px)', color: '#fff', lineHeight: 1.08, margin: 0 }}>
            Things to do in <em style={{ color: '#b9aef5' }}>{cityLabel}</em>
          </div>
          <p style={{ color: 'rgba(255,255,255,0.72)', fontSize: 16, margin: '8px 0 0' }}>Discover the best events, live music, food, and more.</p>
        </div>
      {/* Search + filter chips — no card/box: the search bar and filters sit
          directly on the hero photo. position+zIndex stay so the results
          dropdown still paints above the event cards below. */}
      <div style={{
        position: 'relative', zIndex: 100, marginBottom: 18,
      }}>
        <div style={{ position: 'relative', margin: '0 auto 16px', maxWidth: 560 }}>
          <input
            ref={searchInputRef}
            type="text"
            placeholder="Search bands, venues, or what to do..."
            value={searchQuery}
            onChange={(e) => {
              const v = e.target.value
              // Starting a search (empty -> text) auto-switches When to 'all
              // upcoming' — someone searching "music" wants all upcoming music,
              // not just today's. The day default stays 'today' for browsing.
              if (v.trim() && !searchQuery.trim() && dayFilter === 'today') setDayFilter('all')
              setSearchQuery(v)
              setDropdownOpen(true)
            }}
            onFocus={() => setDropdownOpen(true)}
            style={{
              width: '100%', padding: '14px 20px', fontSize: 15,
              border: '1px solid rgba(0,0,0,0.06)', borderRadius: 999,
              color: '#1a1830', boxSizing: 'border-box',
              background: '#fff',
              boxShadow: '0 6px 24px rgba(0,0,0,0.18)',
              outline: 'none',
            }}
            className="v2-search-input on-light"
          />
          {dropdownOpen && (
            <div ref={dropdownRef} style={{
              position: 'absolute', top: 'calc(100% + 6px)', left: 0, right: 0,
              boxSizing: 'border-box',
              background: '#221a3a', border: '1px solid rgba(255,255,255,0.12)',
              borderRadius: 12, zIndex: 300, overflow: 'visible',
              boxShadow: '0 12px 40px rgba(0,0,0,0.4)',
            }}>
              {/* Unified filters: same When/Time/Vibe dropdowns as under the
                  search bar, driving the shared dayFilter/timeFilter/activeCategories
                  state so they actually filter the search results. */}
              <div style={{
                padding: '10px 14px', borderBottom: '1px solid rgba(255,255,255,0.06)',
                background: 'rgba(127,119,221,0.05)',
                display: 'flex', gap: 8, flexWrap: 'wrap',
                alignItems: 'flex-start', justifyContent: 'flex-start',
                position: 'relative', zIndex: 2,
              }}>
                {/* Single date pill (matches hero): From/To range picker.
                    onFieldFocus arms suppressOutsideRef so the native date
                    picker popup doesn't trip the dropdown's outside-close. */}
                <DateRangeDropdown
                  label={'When: ' + (dayFilter === 'pickdate' ? dateRangeLabel : (({all:'All upcoming',today:'Today · '+todayDow,tomorrow:'Tomorrow',weekend:'This weekend','7days':'Next 7 days'} as Record<string,string>)[dayFilter] || 'All upcoming'))}
                  from={pickedDate}
                  to={dayFilter === 'pickdate' ? pickedEndDate : ''}
                  onFieldFocus={() => { suppressOutsideRef.current = Date.now() + 60000 }}
                  onFrom={(v) => { setPickedDate(v); setDayFilter('pickdate'); suppressOutsideRef.current = 0 }}
                  onTo={(v) => { setPickedEndDate(v); setDayFilter('pickdate'); suppressOutsideRef.current = 0 }}
                  onToday={() => { setPickedDate(v2DateToStr(v2TodayMountain())); setPickedEndDate(''); setDayFilter('today') }}
                  onTomorrow={() => { setPickedEndDate(''); setDayFilter('tomorrow') }}
                  onWeekend={() => { setPickedEndDate(''); setDayFilter('weekend') }}
                  onNext7={() => { setPickedEndDate(''); setDayFilter('7days') }}
                  onAllUpcoming={() => { setPickedEndDate(''); setDayFilter('all') }}
                />
                <FilterDropdown
                  label={'Time: ' + (({any:'Any time',morning:'Morning',afternoon:'Afternoon',evening:'Evening',latenight:'Late night'} as Record<string,string>)[timeFilter] || 'Any time')}
                  value={timeFilter}
                  options={[
                    { value: 'any', label: 'Any time' },
                    { value: 'morning', label: 'Morning' },
                    { value: 'afternoon', label: 'Afternoon' },
                    { value: 'evening', label: 'Evening' },
                    { value: 'latenight', label: 'Late night' },
                  ]}
                  onChange={(v) => setTimeFilter(v as V2TimeFilter)}
                />
                <MultiFilterDropdown
                  label={'Vibe: ' + (activeCategories.size === 0 ? 'All categories' : activeCategories.size === 1 ? Array.from(activeCategories)[0] : activeCategories.size + ' selected')}
                  selected={activeCategories}
                  options={V2_ALL_CATEGORIES.map(cat => ({ value: cat, label: cat }))}
                  onToggle={(v) => setActiveCategories(prev => { const n = new Set(prev); if (n.has(v)) n.delete(v); else n.add(v); return n })}
                  onClear={() => setActiveCategories(new Set())}
                />
                {/* Quick pills mirrored from the hero row so they stay visible
                    while the search dropdown is open (same shared state). */}
                <V2Chip active={freeOnly} onClick={() => setFreeOnly(v => !v)}>Free</V2Chip>
                <V2Chip active={activeCategories.has('Music')} onClick={() => setActiveCategories(prev => { const n = new Set(prev); if (n.has('Music')) n.delete('Music'); else n.add('Music'); return n })}>Music</V2Chip>
                <V2Chip active={activeCategories.has('Food & Drink')} onClick={() => setActiveCategories(prev => { const n = new Set(prev); if (n.has('Food & Drink')) n.delete('Food & Drink'); else n.add('Food & Drink'); return n })}>Food & Drink</V2Chip>
                <input
                  ref={pickDateInputRef}
                  type="date"
                  value={dayFilter === 'pickdate' ? pickedDate : ''}
                  onChange={(e) => {
                    const v = e.target.value
                    if (v) { setPickedDate(v); setDayFilter('pickdate') }
                    suppressOutsideRef.current = 0
                  }}
                  style={{ position: 'absolute', opacity: 0, width: 0, height: 0, padding: 0, border: 0, pointerEvents: 'none' }}
                />
                {(dayFilter !== 'today' || timeFilter !== 'any' || activeCategories.size > 0 || freeOnly || searchQuery.trim()) && (
                  <button type="button"
                    onClick={() => {
                      setSearchQuery('')
                      setDayFilter('today')
                      setTimeFilter('any')
                      setActiveCategories(new Set())
                      setFreeOnly(false)
                      setPickedEndDate('')
                      setShowMoreFilters(false)
                      setDropdownOpen(false)
                    }}
                    style={{
                      background: 'rgba(26,24,48,0.5)',
                      color: '#fff',
                      border: '1px solid rgba(255,255,255,0.18)',
                      borderRadius: 999, padding: '7px 14px', fontSize: 13,
                      fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit',
                    }}>Clear</button>
                )}
              </div>
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
                        display: 'flex', alignItems: 'center', gap: 6,
                        whiteSpace: 'nowrap', overflow: 'hidden',
                      }}>
                        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {ev.venue_name || ev.location || ev.source || ''}
                        </span>
                        {(() => {
                          const sc = ev._sourceCity
                          const cityName = ({parkcity:'Park City',heber:'Heber Valley',jackson:'Jackson Hole',elkhartlake:'Elkhart Lake'} as Record<string,string>)[sc || '']
                          // Only badge events from a DIFFERENT city than the one being browsed.
                          if (!cityName || !sc || sc === (cityKeyProp || 'parkcity')) return null
                          return (
                            <span style={{
                              background: 'rgba(127,119,221,0.18)',
                              color: '#AFA9EC',
                              borderRadius: 999, padding: '1px 8px',
                              fontSize: 10, fontWeight: 500,
                              flexShrink: 0, whiteSpace: 'nowrap',
                            }}>{cityName}</span>
                          )
                        })()}
                      </div>
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
                >See all {groupedResults.length} {groupedResults.length === 1 ? "event" : "events"} &rarr;</div>
              )}
            </div>
          )}
          
        </div>
      </div>
        {/* Filter panel (mockup layout): one white card with a row of category
            tiles on top and flat quick-filter pills below. visibility (not
            display:none) keeps height reserved when the search dropdown is open. */}
        <div style={{
          visibility: dropdownOpen ? 'hidden' : 'visible',
          background: 'transparent', padding: '4px 14px 28px',
          marginBottom: 0, marginLeft: 'calc(50% - 50vw)', marginRight: 'calc(50% - 50vw)', width: '100vw',
          borderRadius: 0,
          display: 'flex', flexDirection: 'column', gap: 10,
        }}>
          <div style={{ display: 'flex', gap: 6, justifyContent: 'center' }}>
            {V2_CATEGORY_TILES.map(({ label, value, Icon }) => {
              const on = activeCategories.has(value)
              return (
                <button key={value} type="button"
                  onClick={() => setActiveCategories(prev => { const n = new Set(prev); if (n.has(value)) n.delete(value); else n.add(value); return n })}
                  style={{
                    display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 4,
                    flex: '1 1 0', minWidth: 0, maxWidth: 76, padding: '9px 2px', borderRadius: 12, cursor: 'pointer',
                    fontFamily: 'inherit', fontSize: 10.5, fontWeight: 600, lineHeight: 1.15, textAlign: 'center',
                    color: on ? '#fff' : '#3a3550',
                    background: on ? '#7c5cff' : '#fff',
                    border: on ? '1px solid #7c5cff' : '1px solid rgba(255,255,255,0.85)',
                    boxShadow: on ? '0 4px 14px rgba(124,92,255,0.35)' : '0 2px 10px rgba(0,0,0,0.18)',
                    transition: 'background 0.15s, color 0.15s',
                  }}>
                  <Icon size={18} strokeWidth={1.75} />
                  <span>{label}</span>
                </button>
              )
            })}
            {(() => {
              const overflow = V2_ALL_CATEGORIES.filter(c => !V2_CATEGORY_TILES.some(t => t.value === c))
              const anyOn = overflow.some(c => activeCategories.has(c))
              return (
                <MoreTile label="More" Icon={MoreHorizontal} active={anyOn}
                  options={overflow.map(c => ({
                    label: c,
                    selected: activeCategories.has(c),
                    onClick: () => setActiveCategories(prev => { const n = new Set(prev); if (n.has(c)) n.delete(c); else n.add(c); return n }),
                  }))}
                />
              )
            })()}
          </div>
          {(() => {
            const pill = (sel: boolean) => ({
              padding: '6px 14px', borderRadius: 999, cursor: 'pointer',
              fontFamily: 'inherit', fontSize: 12.5, fontWeight: 600, whiteSpace: 'nowrap' as const,
              color: sel ? '#fff' : '#3a3550',
              background: sel ? '#7c5cff' : '#fff',
              border: sel ? '1px solid #7c5cff' : '1px solid rgba(255,255,255,0.85)',
              transition: 'background 0.15s, color 0.15s',
            })
            return (
              <div style={{ display: 'flex', gap: 8, justifyContent: 'center', flexWrap: 'wrap', alignItems: 'center' }}>
                <button type="button" style={pill(freeOnly)} onClick={() => setFreeOnly(v => !v)}>Free</button>
                <button type="button" style={pill(dayFilter === 'today')} onClick={() => { setPickedEndDate(''); setDayFilter('today') }}>Today</button>
                <button type="button" style={pill(dayFilter === 'weekend')} onClick={() => { setPickedEndDate(''); setDayFilter('weekend') }}>This Weekend</button>
                <MoreTile label="More" Icon={CalendarDays} variant="pill"
                  active={['tomorrow','7days','all','pickdate'].includes(dayFilter)}
                  options={[
                    { label: 'Tomorrow', selected: dayFilter === 'tomorrow', onClick: () => { setPickedEndDate(''); setDayFilter('tomorrow') } },
                    { label: 'Next 7 days', selected: dayFilter === '7days', onClick: () => { setPickedEndDate(''); setDayFilter('7days') } },
                    { label: 'All upcoming', selected: dayFilter === 'all', onClick: () => { setPickedEndDate(''); setDayFilter('all') } },
                  ]}
                />
                <RadiusPicker />
              </div>
            )
          })()}

        </div>
      </div>
      {/* Purple band behind the events region (date header + featured +
          list). Full-bleed so it spans the page; cards sit on top. */}
      <div style={{
        background: '#2d2853',
        borderRadius: '0 0 20px 20px',
        marginLeft: 'calc(50% - 50vw)', marginRight: 'calc(50% - 50vw)', width: '100vw',
        marginTop: 0, padding: '14px 14px 28px', boxSizing: 'border-box',
      }}>
      <div style={{ maxWidth: 1100, margin: '0 auto' }}>
      <div style={{
        // Desktop: 3-column grid (1fr auto 1fr) centers the date label
        // regardless of side widths. Mobile: stack vertically + center so the
        // title doesn't wrap to 4 lines and eat the screen.
        display: isMobile ? 'flex' : 'grid',
        flexDirection: isMobile ? 'column' : undefined,
        gridTemplateColumns: isMobile ? undefined : '1fr auto 1fr',
        alignItems: 'center',
        gap: isMobile ? 8 : 12, margin: '4px 0 18px',
        textAlign: isMobile ? 'center' : undefined,
      }}>
        <div style={{ fontFamily: "'DM Serif Display', serif", fontSize: isMobile ? 19 : 24, color: '#fff', justifySelf: isMobile ? 'center' : 'start' }}>{({ today: 'Today in ', tomorrow: 'Tomorrow in ', weekend: 'This Weekend in ', '7days': 'This Week in ', all: 'Upcoming in ', pickdate: 'Events in ' } as Record<string, string>)[dayFilter] || 'Today in '}{cityLabel}</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, justifyContent: 'center', justifySelf: 'center' }}>
          <button onClick={shiftDay(-1)} style={{
            background: 'rgba(255,255,255,0.10)', border: '1px solid rgba(255,255,255,0.25)',
            color: '#fff', width: 36, height: 36, borderRadius: '50%',
            fontSize: 18, cursor: 'pointer', lineHeight: 1, flexShrink: 0,
          }} title="Previous day">‹</button>
          <div style={{
            fontSize: isMobile ? 16 : 22, fontWeight: 600, color: '#fff',
            fontFamily: "'DM Serif Display', serif", textAlign: 'center',
          }}>
            {dateRangeLabel}
          </div>
          <button onClick={shiftDay(1)} style={{
            background: 'rgba(255,255,255,0.10)', border: '1px solid rgba(255,255,255,0.25)',
            color: '#fff', width: 36, height: 36, borderRadius: '50%',
            fontSize: 18, cursor: 'pointer', lineHeight: 1, flexShrink: 0,
          }} title="Next day">›</button>
        </div>
        <div style={{
          fontFamily: "'DM Serif Display', serif", fontSize: isMobile ? 17 : 24, color: '#fff',
          whiteSpace: 'nowrap', justifySelf: isMobile ? 'center' : 'end',
        }}>
          {loading ? '' : `${filteredEvents.length} event${filteredEvents.length !== 1 ? 's' : ''}`}
        </div>
      </div>
      {/* Featured events: gold-outlined photo cards, 3-up */}
      {featuredEvents.length > 0 && (
        <div style={{
          fontSize: 20, fontWeight: 800, letterSpacing: 0.4, textTransform: 'uppercase',
          color: '#e0a83a', margin: '0 0 14px',
        }}>{
          dayFilter === 'tomorrow' ? 'Featured Tomorrow'
          : dayFilter === 'weekend' ? 'Featured This Weekend'
          : dayFilter === '7days' ? 'Featured This Week'
          : dayFilter === 'pickdate' ? 'Featured'
          : dayFilter === 'all' ? 'Featured'
          : 'Featured Today'
        }</div>
      )}
      {featuredEvents.length > 0 && (() => {
        const wk = (featuredEvents as any[]).filter(e => e._featuredDay)
        const isWeekend = wk.length > 0
        // Column-major day layout for weekend: order days, render a header
        // row + a grid that fills DOWN each day-column (gridAutoFlow: column).
        const DOWF = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat']
        const days = isWeekend ? Array.from(new Set(wk.map(e => e._featuredDay))).sort() : []
        const ordered = isWeekend
          ? days.flatMap(day => (featuredEvents as any[]).filter(e => e._featuredDay === day))
          : (featuredEvents as any[])
        const maxPerDay = isWeekend ? Math.max(...days.map(day => (featuredEvents as any[]).filter(e => e._featuredDay === day).length)) : 0
        return (
          <div style={{ margin: '0 0 28px' }}>
            {isWeekend && (
              <div style={{ display: 'grid', gridTemplateColumns: `repeat(${days.length}, 1fr)`, gap: 6, marginBottom: 8 }}>
                {days.map(day => {
                  const [y, m, d] = day.split('-').map(Number)
                  const dn = new Date(y, m - 1, d)
                  const full = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'][dn.getDay()]
                  return <div key={day} style={{ fontSize: 13, fontWeight: 700, color: '#fff', textAlign: 'center' }}>{full}</div>
                })}
              </div>
            )}
            <div style={{
              display: 'grid',
              gridTemplateColumns: isWeekend ? `repeat(${days.length}, 1fr)` : 'repeat(3, 1fr)',
              gridTemplateRows: isWeekend ? `repeat(${maxPerDay}, auto)` : undefined,
              gridAutoFlow: isWeekend ? 'column' : 'row',
              gap: 6,
              alignItems: 'stretch',
            }}>
              {ordered.map((ev, i) => (
                <V2FeaturedCard key={`featured-${ev.title}-${ev.date}-${i}`} event={ev} onClick={() => handleEventClick(ev)} viewedDay={ev._featuredDay || viewedDayStr} />
              ))}
            </div>
          </div>
        )
      })()}
      
      {loading ? (
        <div style={{ textAlign: 'center', padding: 60, color: 'rgba(255,255,255,0.4)' }}>Loading events…</div>
      ) : filteredEvents.length === 0 ? (
        fallForwardEvents ? (
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', padding: '14px 18px', margin: '0 0 16px', background: 'rgba(127,119,221,0.12)', border: '1px solid rgba(175,169,236,0.3)', borderRadius: 12, fontSize: 14 }}>
              <span style={{ color: 'rgba(255,255,255,0.8)' }}>{fallForwardEvents.emptyLabel} that matches your filters.</span>
              <span style={{ color: '#AFA9EC', fontWeight: 700 }}>Next up — {fallForwardEvents.pretty}:</span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(min(440px, 100%), 1fr))', gap: 8 }}>
              {fallForwardEvents.events.map((ev, i) => (
                <V2EventCard key={`ff-${ev.title}-${ev.date}-${i}`} event={ev} onClick={() => handleEventClick(ev)} viewedDay={fallForwardEvents.date} />
              ))}
            </div>
          </div>
        ) : (
          <div style={{ textAlign: 'center', padding: 60, color: 'rgba(255,255,255,0.6)', background: 'rgba(255,255,255,0.04)', borderRadius: 14, border: '1px solid rgba(255,255,255,0.1)' }}>
            No events match your filters. Try widening the time range or clearing search.
          </div>
        )
      ) : groupedByDay ? (
        // Range view: events grouped under a day header (Fri, then Sat, ...).
        <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
          {groupedByDay.map(group => (
            <div key={group.dateStr}>
              <div style={{
                fontFamily: "'DM Serif Display', serif", fontSize: 16, color: '#fff',
                margin: '0 0 10px', paddingBottom: 6,
                borderBottom: '1px solid rgba(255,255,255,0.12)',
              }}>{group.label}</div>
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(min(440px, 100%), 1fr))',
                gap: 8,
              }}>
                {group.events.map((ev, i) => (
                  <V2EventCard key={`${group.dateStr}-${ev.title}-${i}`} event={ev} onClick={() => handleEventClick(ev)} viewedDay={group.dateStr} />
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(min(440px, 100%), 1fr))',
          gap: 8,
        }}>
          {filteredEvents.map((ev, i) => (
            <V2EventCard key={`${ev.title}-${ev.date}-${i}`} event={ev} onClick={() => handleEventClick(ev)} viewedDay={viewedDayStr} />
          ))}
        </div>
      )}
      </div>
      </div>
      {mounted && showResultsView && createPortal((
        <div
          onClick={() => setShowResultsView(false)}
          style={{
            position: 'fixed', inset: 0, zIndex: 9999,
            background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(8px)',
            display: 'flex', flexDirection: 'column',
            overflowY: 'auto',
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              maxWidth: 720, margin: '24px auto', width: 'calc(100% - 32px)', boxSizing: 'border-box',
              background: '#1B1638', borderRadius: 16,
              border: '1px solid rgba(255,255,255,0.08)',
              padding: '16px 16px 24px',
              boxShadow: '0 24px 60px rgba(0,0,0,0.5)',
            }}
          >
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              marginBottom: 16, paddingBottom: 12,
              borderBottom: '1px solid rgba(255,255,255,0.08)',
            }}>
              <div>
                <button
                  type="button"
                  onClick={() => setShowResultsView(false)}
                  style={{
                    background: 'transparent', border: 'none', color: '#AFA9EC',
                    cursor: 'pointer', fontSize: 13, fontFamily: 'inherit',
                    padding: 0, marginBottom: 4,
                  }}
                >&larr; Back to calendar</button>
                <div style={{ color: '#fff', fontSize: 18, fontWeight: 600 }}>
                  {groupedResults.length} {groupedResults.length === 1 ? 'event' : 'events'}
                  {searchQuery.trim() ? ` matching "${searchQuery.trim()}"` : ''}
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShowResultsView(false)}
                aria-label="Close"
                style={{
                  background: 'rgba(255,255,255,0.08)', border: 'none',
                  color: '#fff', borderRadius: 8, width: 32, height: 32,
                  cursor: 'pointer', fontSize: 18, fontFamily: 'inherit',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}
              >×</button>
            </div>
            {/* City filter pills — Model C cross-city UX. Default to current
                city, user can expand to all or pick a specific city. */}
            <div style={{
              display: 'flex', flexWrap: 'wrap', gap: 6,
              marginBottom: 14, paddingBottom: 12,
              borderBottom: '1px solid rgba(255,255,255,0.06)',
            }}>
              {([
                { id: 'current' as CityFilterValue, label: ({parkcity:'Park City',heber:'Heber Valley',jackson:'Jackson Hole',elkhartlake:'Elkhart Lake'} as Record<string,string>)[(cityKeyProp || 'parkcity')] || 'Local' },
                { id: 'parkcity' as CityFilterValue, label: 'Park City' },
                { id: 'heber' as CityFilterValue, label: 'Heber Valley' },
                { id: 'jackson' as CityFilterValue, label: 'Jackson Hole' },
                { id: 'elkhartlake' as CityFilterValue, label: 'Elkhart Lake' },
                { id: 'all' as CityFilterValue, label: 'All cities' },
              ]).filter(p => {
                // Don't show the current-city pill twice: when on Heber, hide
                // the 'Heber Valley' pill since 'current' already covers it.
                const currentMap: Record<string, CityFilterValue> = {parkcity:'parkcity',heber:'heber',jackson:'jackson',elkhartlake:'elkhartlake'}
                const ck = currentMap[cityKeyProp || 'parkcity']
                return !(p.id === ck && p.id !== 'current')
              }).map(p => {
                const active = cityFilter === p.id
                return (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => setCityFilter(p.id)}
                    style={{
                      background: active ? '#534AB7' : 'rgba(255,255,255,0.08)',
                      color: active ? '#fff' : 'rgba(255,255,255,0.78)',
                      border: active ? '1px solid transparent' : '1px solid rgba(255,255,255,0.12)',
                      borderRadius: 999, padding: '4px 11px', fontSize: 11,
                      fontWeight: active ? 500 : 400, cursor: 'pointer',
                      fontFamily: 'inherit',
                    }}
                  >{p.label}</button>
                )
              })}
            </div>
            {groupedResults.length === 0 ? (
              <div style={{
                color: 'rgba(255,255,255,0.55)', textAlign: 'center',
                padding: '40px 16px', fontSize: 14,
              }}>
                No events match. Try a different search or clear filters.
              </div>
            ) : (
              <div>
                {groupedResults.map((group, gi) => {
                  const isExpanded = expandedGroups.has(group.key)
                  const nextEv = group.occurrences[0]
                  const d = v2ParseEventDate((nextEv.date || '').slice(0, 10))
                  const MON = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
                  const DOW = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat']
                  const datePill = d ? `${DOW[d.getDay()]} ${MON[d.getMonth()]} ${d.getDate()}` : ''
                  const hasMore = group.occurrences.length > 1
                  return (
                    <div key={`grp-${gi}`} style={{
                      borderBottom: '1px solid rgba(255,255,255,0.06)',
                    }}>
                      <div
                        onClick={(e) => {
                          e.stopPropagation()
                          if (group.occurrences.length === 1) {
                            handleEventClick(group.occurrences[0])
                            // Keep overlay open: modal renders on top, closing
                            // modal returns to overlay with state preserved.
                          } else {
                            setExpandedGroups(prev => {
                              const next = new Set(prev)
                              if (next.has(group.key)) next.delete(group.key)
                              else next.add(group.key)
                              return next
                            })
                          }
                        }}
                        style={{
                          padding: '12px 4px', display: 'flex',
                          alignItems: 'center', gap: 12, cursor: 'pointer',
                        }}
                      >
                        <div style={{
                          background: '#534AB7', color: '#fff',
                          borderRadius: 8, padding: '4px 8px',
                          fontSize: 11, fontWeight: 500, minWidth: 64,
                          textAlign: 'center', flexShrink: 0,
                        }}>{datePill}</div>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{
                            color: '#fff', fontSize: 14, fontWeight: 500,
                            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                          }}>{nextEv.title}</div>
                          <div style={{
                            color: 'rgba(255,255,255,0.55)', fontSize: 12,
                            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                            display: 'flex', alignItems: 'center', gap: 6,
                          }}>
                            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>
                              {nextEv.venue_name || nextEv.location || nextEv.source || ''}
                              {hasMore ? ` · ${group.occurrences.length} dates` : ''}
                            </span>
                            {(() => {
                              const cityKey = nextEv._sourceCity || cityKeyProp || ''
                              const cityName = ({parkcity:'Park City',heber:'Heber Valley',jackson:'Jackson Hole',elkhartlake:'Elkhart Lake'} as Record<string,string>)[cityKey]
                              if (!cityName) return null
                              return (
                                <span style={{
                                  background: 'rgba(127,119,221,0.18)',
                                  color: '#AFA9EC',
                                  borderRadius: 999, padding: '1px 8px',
                                  fontSize: 10, fontWeight: 500,
                                  flexShrink: 0, whiteSpace: 'nowrap',
                                }}>{cityName}</span>
                              )
                            })()}
                          </div>
                        </div>
                        {hasMore && (
                          <div style={{
                            color: '#AFA9EC', fontSize: 18,
                            transform: isExpanded ? 'rotate(90deg)' : 'rotate(0deg)',
                            transition: 'transform 120ms ease',
                            flexShrink: 0, paddingRight: 4,
                          }}>›</div>
                        )}
                      </div>
                      {isExpanded && hasMore && (
                        <div style={{
                          paddingLeft: 76, paddingBottom: 8,
                          display: 'flex', flexDirection: 'column', gap: 6,
                        }}>
                          {group.occurrences.map((occ, oi) => {
                            const od = v2ParseEventDate((occ.date || '').slice(0, 10))
                            const odLabel = od
                              ? `${DOW[od.getDay()]}, ${MON[od.getMonth()]} ${od.getDate()}`
                              : (occ.date || '')
                            return (
                              <div
                                key={`occ-${oi}`}
                                onClick={(e) => {
                                  e.stopPropagation()
                                  handleEventClick(occ)
                                  // Keep overlay open so the modal can close
                                  // back to the expanded-date list.
                                }}
                                style={{
                                  color: 'rgba(255,255,255,0.75)', fontSize: 13,
                                  padding: '6px 8px', borderRadius: 6,
                                  cursor: 'pointer',
                                  background: 'rgba(255,255,255,0.04)',
                                }}
                              >
                                {odLabel}{occ.start_time ? ` · ${occ.start_time}` : ''}
                              </div>
                            )
                          })}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      ), document.body)}
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

