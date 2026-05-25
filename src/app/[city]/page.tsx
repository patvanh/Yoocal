import { notFound } from 'next/navigation'
import type { Metadata } from 'next'
import { CITY_CONFIG, cityKeyFromSlug, getEventsForCity, type CityKey } from '@/lib/events'
import CityLanding from '@/components/CityLanding'

interface Props {
  params: Promise<{ city: string }>
}

// Pre-build all four city landing pages as static HTML for SEO.
export const dynamicParams = false

export async function generateStaticParams() {
  return Object.values(CITY_CONFIG).map((c) => ({ city: c.slug }))
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { city } = await params
  const cityKey = cityKeyFromSlug(city)
  if (!cityKey) return {}
  const cfg = CITY_CONFIG[cityKey]
  const cityName = cfg.name.replace(/,.*$/, '').trim() // "Park City, UT" -> "Park City"
  const title = `Things to Do in ${cityName} — Events Calendar | Yoocal`
  const description = `Find everything happening in ${cfg.name} — concerts, festivals, races, outdoor adventures, food, and family events. Updated daily, free for locals and visitors.`
  const url = `https://www.yoocal.com/${cfg.slug}`
  return {
    title,
    description,
    openGraph: {
      title,
      description,
      url,
      images: [{ url: '/og-image.png', width: 1200, height: 630 }],
    },
    alternates: { canonical: url },
  }
}

export default async function CityPage({ params }: Props) {
  const { city } = await params
  const cityKey = cityKeyFromSlug(city)
  if (!cityKey) notFound()
  return <CityLanding citySlug={city} cityKey={cityKey} />
}
