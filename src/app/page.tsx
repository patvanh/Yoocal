import type { Metadata } from 'next'
import { Suspense } from 'react'
import HomeRouter from '@/components/HomeRouter'
import HomeServer from '@/components/HomeServer'

// HomeRouter (client) still handles the interactive brand view and the
// legacy ?city= redirect; it's wrapped in Suspense for useSearchParams.
// HomeServer renders the canonical brand/city content into the HTML so the
// homepage isn't a client-only shell to crawlers.

export const metadata: Metadata = {
  title: 'Yoocal — Local events in scenic towns across the US',
  description:
    'One place for everything happening in scenic resort towns and mountain communities — concerts, festivals, races, outdoor adventures, and more. Free, updated daily.',
  openGraph: {
    title: 'Yoocal — Local events in scenic towns',
    description:
      'One place for everything happening in scenic resort towns. Free, updated daily for locals and visitors alike.',
    url: 'https://www.yoocal.com',
    images: [{ url: '/og-image.png', width: 1200, height: 630 }],
  },
  alternates: { canonical: 'https://www.yoocal.com/' },
}

export default function Home() {
  return (
    <>
      <Suspense fallback={null}>
        <HomeRouter />
      </Suspense>
      <HomeServer />
    </>
  )
}
