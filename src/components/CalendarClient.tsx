'use client'

import { useEffect } from 'react'

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
  useEffect(() => {
    // ── All initialization JavaScript ──
    // This is the full calendar app logic, adapted from the original index.html

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
      else if (event.is_free === false && event.price && event.price !== '0') cats.push('paid')
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
        if (!overrideDisplayDate && endDate && endDate !== startDate) displayDay += '+'
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
      return `<div class="cal-event${featured?' featured':''}" data-categories="${cats}" data-start="${startStr}" data-end="${endStr}" data-recurrence="${event.recurrence||''}" data-recurrence-day="${event.recurrence_day||''}" data-recurrence-days="${event.recurrence_days||''}" data-lat="${event.lat||''}" data-lng="${event.lng||''}" data-title="${(event.title||'').replace(/"/g,'&quot;')}" data-location="${(event.location||'').replace(/"/g,'&quot;')}" data-date="${event.date||''}" data-end-date="${event.end_date||''}" data-link="${event.link||''}" data-description="${(event.description||'').replace(/"/g,'&quot;').replace(/\n/g,' ')}" data-source="${sourceShort}" data-start-time="${event.start_time||''}" data-end-time="${event.end_time||''}" onclick="openEventModal(this)" style="cursor:pointer"><div class="cal-event-time"><div class="h">${displayMonth}</div><div class="ap">${displayDay}</div>${event.start_time?`<div style="font-size:15px;font-weight:600;color:white;line-height:1;margin-top:2px;white-space:nowrap">${event.start_time}</div>`:''}</div><div class="cal-event-info"><h4>${event.title}</h4><p>${(event.description||'').slice(0,120)||'See website for details.'}</p><div class="cal-tags">${tagHTML}<span class="cal-source">via ${sourceShort}${distLabel}</span></div></div><div class="cal-event-actions"><button class="atc-btn" title="Add to calendar" onclick="openAtcDropdown(event,this)">📅</button></div></div>`
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
          return `<div class="featured-band-card" onclick="openEventModal(this)" data-title="${(e.title||'').replace(/"/g,'&quot;')}" data-date="${e.date||''}" data-end-date="${e.end_date||''}" data-location="${(e.location||'').replace(/"/g,'&quot;')}" data-link="${e.link||''}" data-description="${(e.description||'').replace(/"/g,'&quot;').replace(/\n/g,' ')}" data-source="${(e.source||'').replace(/"/g,'&quot;')}" data-categories="${cats.join(' ')}" data-start-time="${e.start_time||''}" data-end-time="${e.end_time||''}" style="cursor:pointer"><div class="fbc-time"><div class="h">${month}</div><div class="ap">${day}</div>${e.start_time?`<div style="font-size:9px;color:rgba(255,255,255,0.6);margin-top:3px;white-space:nowrap">${e.start_time}</div>`:''}</div><div class="fbc-info"><h4>${e.title}</h4><p>${(e.description||'').slice(0,100)||(e.location?'📍 '+e.location:'')}</p><div class="cal-tags" style="margin-top:6px">${tagHTML}<span class="cal-source">via ${src}</span></div></div></div>`
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
        if (heroStat) heroStat.textContent = String(allEvents.filter((e: any) => !e._supplemental).length)
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
      if (location) meta.push(`<div style="display:flex;align-items:center;gap:10px;font-size:14px;color:rgba(255,255,255,0.7)"><span style="font-size:16px">📍</span>${location}</div>`)
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
      const dtStart = toICSTime(dateStr, startTime), dtEnd = toICSTime(dateStr, endTime||startTime)
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
      const gStart = toCalTime(dateStr, startTime), gEnd = startTime ? toCalTime(dateStr, endTime||startTime) : dateStr.replace(/-/g,'')
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
          <a href="#business">For businesses</a>
          <a href="https://forms.groupmail.info/subscribe/yoocal" target="_blank" rel="noopener noreferrer" className="nav-cta">Get notified</a>
        </div>
      </nav>

      {/* HERO */}
      <div className="hero-wrapper">
        <section className="hero">
          <div className="hero-bg" />
          <h1>Your local,<br /><em>everywhere.</em></h1>
          <p>One place for everything happening near you — for locals and visitors alike. Updated daily from every source that matters.</p>
          <div style={{display:'flex',flexDirection:'column',alignItems:'center',gap:'12px',animation:'fadeUp 0.6s 0.3s ease both',width:'100%',maxWidth:'480px'}}>
            <button id="hero-locate-btn" onClick={() => window.heroUseMyLocation?.()} style={{display:'inline-flex',alignItems:'center',gap:'10px',background:'var(--purple)',color:'white',border:'none',padding:'14px 32px',borderRadius:'100px',fontSize:'15px',fontWeight:600,cursor:'pointer',transition:'background 0.2s',whiteSpace:'nowrap'}}>
              📍 Use my location
            </button>
            <div style={{display:'flex',alignItems:'center',gap:'10px',width:'100%'}}>
              <div style={{flex:1,height:'1px',background:'rgba(255,255,255,0.4)'}} />
              <span style={{fontSize:'13px',color:'rgba(255,255,255,0.85)',whiteSpace:'nowrap'}}>or search by city, town, or zip</span>
              <div style={{flex:1,height:'1px',background:'rgba(255,255,255,0.4)'}} />
            </div>
            <div style={{position:'relative',width:'100%'}}>
              <input id="hero-location-input" type="text" placeholder="e.g. Park City, UT or 84060"
                style={{width:'100%',background:'rgba(255,255,255,0.08)',border:'1px solid rgba(255,255,255,0.2)',color:'white',padding:'13px 20px',borderRadius:'100px',fontSize:'14px',outline:'none',fontFamily:"'DM Sans',sans-serif",transition:'border-color 0.2s'}}
              />
            </div>
          </div>
          <div className="hero-stats" style={{marginTop:'48px'}}>
            <div className="hero-stat"><span className="num" id="hero-event-count">1,451</span><span className="label">Events this week</span></div>
            <div className="hero-stat"><span className="num">Free</span><span className="label">Always, for everyone</span></div>
          </div>
        </section>

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
          <a href="#" className="loc-chip" onClick={(e) => { e.preventDefault(); window.switchCity?.('parkcity', e.currentTarget as HTMLElement) }} data-city="parkcity">📍 Park City, UT</a>
          <a href="#" className="loc-chip" onClick={(e) => { e.preventDefault(); window.switchCity?.('elkhartlake', e.currentTarget as HTMLElement) }} data-city="elkhartlake">📍 Elkhart Lake, WI</a>
          <a href="#signup" className="loc-chip" style={{opacity:0.5}}>+ Aspen, CO — coming soon</a>
          <a href="#signup" className="loc-chip" style={{opacity:0.5}}>+ Jackson Hole, WY — coming soon</a>
        </div>
      </div>

      {/* HOW IT WORKS */}
      <section className="section" id="how" style={{padding:'60px 80px'}}>
        <div style={{display:'flex',alignItems:'center',gap:'80px',maxWidth:'1100px',margin:'0 auto'}}>
          <div style={{flex:1}}>
            <div className="section-label">How it works</div>
            <h2>Stop checking <em>seven</em> different sites.</h2>
            <p style={{marginTop:'16px'}}>We automatically gather events from every local source — newspapers, Facebook groups, venue websites, chamber listings — and put them all in one clean calendar.</p>
          </div>
          <div style={{flex:1,display:'flex',flexDirection:'column',gap:'16px'}}>
            <div className="step reveal" style={{margin:0}}>
              <div className="step-icon">🔍</div>
              <h3>We scrape daily</h3>
              <p>Our engine checks local newspapers, Eventbrite, chamber websites, and venue pages every single day.</p>
            </div>
            <div className="step reveal" style={{margin:0}}>
              <div className="step-icon">📬</div>
              <h3>We email your weekend</h3>
              <p>Subscribe to get &quot;This Weekend&quot; in your inbox every Thursday — curated, local, and free.</p>
            </div>
          </div>
        </div>
      </section>

      {/* CALENDAR */}
      <section className="calendar-section" id="events">
        <div className="section-label">Live calendar</div>
        <h2>What&apos;s happening <em>now</em></h2>
        <p style={{marginBottom:'40px'}}>Park City &amp; Summit County — updated daily</p>
        <div className="cal-ui">
          <div className="cal-topbar">
            <div className="cal-logo"><div className="cal-logo-dot" /> yoocal</div>
            <div className="cal-view-toggle">
              <button className="cal-view-btn active" id="btn-list" onClick={() => window.setView?.('list')}>☰ List</button>
              <button className="cal-view-btn" id="btn-map" onClick={() => window.setView?.('map')}>🗺 Map</button>
            </div>
            <div className="cal-loc" id="cal-loc-label" onClick={(e) => window.toggleEyebrowDropdown?.(e.nativeEvent)} style={{cursor:'pointer',userSelect:'none'}}>📍 Park City, UT &nbsp;▾</div>
          </div>
          <div className="cal-search">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
            <input type="text" id="event-search" placeholder="Search events, venues, categories..." autoComplete="off" />
            <button id="search-clear" aria-label="Clear search" style={{display:'none'}}>✕</button>
          </div>
          <div className="cal-filters">
            {[['all','All'],['music','🎵 Music'],['outdoor','🌲 Outdoor'],['food','🍽 Food & Drink'],['arts','🎨 Arts'],['sports','⛷ Sports'],['family','👨‍👩‍👧 Family'],['wellness','🧘 Wellness'],['community','🤝 Community'],['free','🆓 Free'],['paid','🎟 Paid']].map(([f,l]) => (
              <div key={f} className={`cal-filter${f==='all'?' active':''}`} data-filter={f}>{l}</div>
            ))}
          </div>
          {/* Radius filter */}
          <div id="radius-bar" style={{display:'flex',alignItems:'center',gap:'10px',padding:'10px 24px',borderBottom:'1px solid rgba(255,255,255,0.06)',flexWrap:'wrap'}}>
            <button id="radius-locate-btn" onClick={() => window.useMyLocation?.()} style={{display:'inline-flex',alignItems:'center',gap:'6px',background:'rgba(255,255,255,0.07)',border:'1px solid rgba(255,255,255,0.15)',color:'white',padding:'6px 14px',borderRadius:'100px',fontSize:'13px',fontWeight:500,cursor:'pointer',whiteSpace:'nowrap',transition:'all 0.15s'}}>📍 Use my location</button>
            <span style={{color:'rgba(255,255,255,0.3)',fontSize:'13px'}}>or</span>
            <input id="radius-zip" type="text" placeholder="City, state or zip code" maxLength={100} style={{background:'rgba(255,255,255,0.07)',border:'1px solid rgba(255,255,255,0.15)',color:'white',padding:'6px 14px',borderRadius:'100px',fontSize:'13px',width:'200px',outline:'none'}} />
            <div id="radius-slider-wrap" style={{display:'none',alignItems:'center',gap:'8px'}}>
              <span style={{fontSize:'13px',color:'rgba(255,255,255,0.5)',whiteSpace:'nowrap'}}>Within</span>
              <input id="radius-slider" type="range" min="5" max="50" defaultValue="25" step="5" style={{width:'100px',accentColor:'var(--purple)'}} onInput={(e) => window.onRadiusChange?.((e.target as HTMLInputElement).value)} />
              <span id="radius-label" style={{fontSize:'13px',fontWeight:600,color:'white',whiteSpace:'nowrap',minWidth:'50px'}}>25 mi</span>
              <button onClick={() => window.clearRadius?.()} style={{background:'none',border:'none',color:'rgba(255,255,255,0.4)',fontSize:'18px',cursor:'pointer',lineHeight:1,padding:'0 4px'}} title="Clear">✕</button>
            </div>
            <span id="radius-status" style={{fontSize:'12px',color:'rgba(255,255,255,0.4)'}} />
          </div>
          {/* Day chips */}
          <div className="cal-days-header" style={{justifyContent:'center',position:'relative'}}>
            <div className="cal-days-label" id="cal-days-label">This week</div>
            <div style={{display:'flex',alignItems:'center',gap:'8px',position:'absolute',right:'24px',top:'50%',transform:'translateY(-50%)'}}>
              <button id="cal-today-btn" onClick={() => window.jumpToToday?.()} style={{display:'none',background:'rgba(255,255,255,0.08)',border:'1px solid rgba(255,255,255,0.15)',color:'white',padding:'4px 12px',borderRadius:'100px',fontSize:'12px',fontWeight:600,cursor:'pointer'}}>↩ Today</button>
              <button className="cal-month-btn" id="cal-month-toggle" title="Pick a date">📅</button>
            </div>
          </div>
          <div style={{display:'flex',alignItems:'center',justifyContent:'center',borderBottom:'1px solid rgba(255,255,255,0.06)',padding:'0 16px'}}>
            <div style={{display:'inline-flex',alignItems:'center'}}>
              <button className="cal-week-arrow" id="cal-prev-week" title="Previous week">‹</button>
              <div className="cal-days" id="cal-days-container" style={{padding:'14px 6px',borderBottom:'none',flexShrink:0}} />
              <button className="cal-week-arrow" id="cal-next-week" title="Next week">›</button>
            </div>
          </div>
          {/* Month picker */}
          <div className="cal-month-picker" id="cal-month-picker" style={{display:'none'}}>
            <div className="cal-month-nav">
              <button id="cal-prev-month">‹</button>
              <span id="cal-month-title" />
              <button id="cal-next-month">›</button>
            </div>
            <div className="cal-month-grid">
              {['Su','Mo','Tu','We','Th','Fr','Sa'].map(d => <div key={d} className="cal-month-dow">{d}</div>)}
            </div>
            <div className="cal-month-days" id="cal-month-days" />
          </div>
          {/* Featured band */}
          <div className="featured-band" id="featured-band" style={{display:'none'}}>
            <div className="featured-band-header"><span className="featured-band-label">⭐ Featured events</span></div>
            <div className="featured-band-cards" id="featured-band-cards" />
          </div>
          {/* Events container */}
          <div className="cal-events" id="cal-events-container">
            <div style={{padding:'32px',textAlign:'center',color:'rgba(255,255,255,0.4)',fontSize:'14px'}}>Loading events...</div>
          </div>
          <div className="cal-no-results" id="no-results" style={{display:'none',padding:'32px',textAlign:'center',color:'rgba(255,255,255,0.4)',fontSize:'14px'}}>No events found for this filter. Check back soon!</div>
          {/* Map view */}
          <div id="cal-map-container" style={{display:'none',height:'600px',width:'100%',position:'relative'}}>
            <div id="cal-map" style={{height:'100%',width:'100%'}} />
          </div>
        </div>
      </section>

      {/* DATA SOURCES */}
      <section className="sources-section reveal" id="sources">
        <div className="section-label">Data sources</div>
        <h2>Every source, <em>in one place</em></h2>
        <p style={{fontSize:'17px',color:'var(--muted)',maxWidth:'480px',lineHeight:1.7,fontWeight:300,marginBottom:0}}>We pull from everywhere locals and visitors actually post events.</p>
        <div className="sources-grid" style={{marginTop:'48px'}}>
          {[['📰','The Park Record','Local newspaper events listings'],['🏛','PC Chamber','Chamber of Commerce calendar'],['👥','Facebook Groups','Local community group posts'],['🎟','Eventbrite','Ticketed events & registrations'],['🗺','Visit Park City','Official tourism events calendar'],['🏔','Venue Websites','Resorts, bars, galleries & more']].map(([icon,name,desc]) => (
            <div key={name} className="source-card reveal"><div className="source-icon">{icon}</div><h4>{name}</h4><p>{desc}</p></div>
          ))}
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
            <a href="https://forms.groupmail.info/subscribe/yoocal" target="_blank" rel="noopener noreferrer" className="biz-btn">Get started free</a>
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
            <div className="footer-col"><h4>Product</h4><a href="#events">Browse events</a><a href="#how">How it works</a><a href="#signup">Newsletter</a></div>
            <div className="footer-col"><h4>Business</h4><a href="#business">List your event</a><a href="mailto:hello@yoocal.com">Advertise</a><a href="mailto:hello@yoocal.com">Partner with us</a></div>
            <div className="footer-col"><h4>Cities</h4><a href="#">Park City, UT</a><a href="#signup">Aspen, CO (soon)</a><a href="#signup">Jackson Hole (soon)</a></div>
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
        <div className="eyebrow-dropdown-divider" />
        <div className="eyebrow-city-option coming-soon">+ Aspen, CO — coming soon</div>
        <div className="eyebrow-city-option coming-soon">+ Jackson Hole, WY — coming soon</div>
      </div>
    </>
  )
}
