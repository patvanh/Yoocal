import type { Metadata } from 'next'
import CalendarClient from '@/components/CalendarClient'

export const metadata: Metadata = {
  title: 'Yoocal — Things To Do in Park City, Utah | Local Events Calendar',
  description: 'Find everything happening in Park City, Utah — concerts, outdoor adventures, festivals, food events, races and more. One free calendar updated daily from every local source.',
  openGraph: {
    title: 'Yoocal — Things To Do in Park City, Utah',
    description: 'One place for everything happening in Park City. Concerts, races, festivals, food events and more — updated daily. Free for locals and visitors.',
    url: 'https://www.yoocal.com',
    images: [{ url: '/og-image.png', width: 1200, height: 630 }],
  },
  alternates: { canonical: 'https://www.yoocal.com/' },
}

export default function Home() {
  return <CalendarClient />
}
