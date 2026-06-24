import { notFound } from 'next/navigation'
import type { Metadata } from 'next'
import { CITY_CONFIG, cityKeyFromSlug, getEventsForCity, slugify, type CityKey } from '@/lib/events'
import CityLanding from '@/components/CityLanding'
import CityHubServer from '@/components/CityHubServer'

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

  // Server-rendered ItemList of upcoming events so this list page is
  // schema-visible to crawlers (the audit flagged list pages as having no
  // ItemList). The visible list is still rendered client-side by CityLanding;
  // this adds machine-readable structure to the HTML without touching that.
  const cfg = CITY_CONFIG[cityKey]
  const cityName = cfg.name.replace(/,.*$/, '').trim()
  const today = new Date().toISOString().slice(0, 10)
  const upcoming = getEventsForCity(cityKey)
    .filter((e) => /^\d{4}-\d{2}-\d{2}/.test(e.date || '') && (e.date || '').slice(0, 10) >= today)
    .sort((a, b) => (a.date || '').localeCompare(b.date || ''))
    .slice(0, 25)

  const itemListSchema = {
    '@context': 'https://schema.org',
    '@type': 'ItemList',
    name: `Upcoming events in ${cityName}`,
    itemListOrder: 'https://schema.org/ItemListOrderAscending',
    numberOfItems: upcoming.length,
    itemListElement: upcoming.map((e, i) => {
      const eventSlug = `${slugify(e.title || '')}-${(e.date || '').slice(0, 10)}`
      return {
        '@type': 'ListItem',
        position: i + 1,
        url: `https://www.yoocal.com/${cfg.slug}/${eventSlug}`,
        name: e.title || 'Event',
      }
    }),
  }

  return (
    <>
      {upcoming.length > 0 && (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(itemListSchema) }}
        />
      )}
      <CityLanding citySlug={city} cityKey={cityKey} />
      <CityHubServer cityKey={cityKey} />
    </>
  )
}
