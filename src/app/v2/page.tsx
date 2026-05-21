'use client'

import { useEffect, useState } from 'react'
import PageShell from '@/components/v2/PageShell'
import HeroSection from '@/components/v2/HeroSection'
import CityChipsBar from '@/components/v2/CityChipsBar'
import FeaturedEvents from '@/components/v2/FeaturedEvents'
import CalendarClientV2 from '@/components/CalendarClientV2'

const CITY_NAMES: Record<string, string> = {
  parkcity: 'Park City, UT',
  heber: 'Heber Valley, UT',
  jackson: 'Jackson Hole, WY',
  elkhartlake: 'Elkhart Lake, WI',
}

const CITY_FILES: Record<string, string> = {
  parkcity: '/events.json',
  heber: '/events-heber.json',
  jackson: '/events-jackson.json',
  elkhartlake: '/events-elkhartlake.json',
}

export default function V2Page() {
  const [cityKey, setCityKey] = useState('parkcity')
  const [eventCount, setEventCount] = useState<number | null>(null)
  
  useEffect(() => {
    fetch(CITY_FILES[cityKey])
      .then(r => r.json())
      .then(d => setEventCount((d.events || d).length))
      .catch(() => setEventCount(null))
  }, [cityKey])
  
  const today = new Date()
  const dayLabel = ['SUN','MON','TUE','WED','THU','FRI','SAT'][today.getDay()]
  const monthLabel = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][today.getMonth()]
  const todayLabel = `${dayLabel}, ${monthLabel} ${today.getDate()}`
  
  return (
    <PageShell cityKey={cityKey as any}>
      <HeroSection
        cityName={CITY_NAMES[cityKey] || 'Park City, UT'}
        todayLabel={todayLabel}
        eventCountThisWeek={eventCount ?? undefined}
      />
      <CityChipsBar
        activeCity={cityKey}
        onCityChange={setCityKey}
      />
      <div style={{ padding: '32px 0' }}>
        <CalendarClientV2 initialCity={cityKey} />
      </div>
    </PageShell>
  )
}
