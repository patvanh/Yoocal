import type { Metadata } from 'next'
import HomeRouter from '@/components/HomeRouter'

// HomeRouter reads query params and localStorage to decide which view
// to render; can't be statically prerendered.
export const dynamic = 'force-dynamic'

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
  return <HomeRouter />
}
