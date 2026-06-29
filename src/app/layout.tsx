import type { Metadata, Viewport } from 'next'
import Script from 'next/script'
import ServiceWorkerRegister from '@/components/ServiceWorkerRegister'
import MetaPixel from '@/components/MetaPixel'
import { DM_Sans, DM_Serif_Display } from 'next/font/google'

const dmSans = DM_Sans({
  subsets: ['latin'],
  weight: ['300', '400', '500', '600'],
  variable: '--font-dm-sans',
  display: 'swap',
})
const dmSerif = DM_Serif_Display({
  subsets: ['latin'],
  weight: '400',
  style: ['normal', 'italic'],
  variable: '--font-dm-serif',
  display: 'swap',
})
import { Analytics } from '@vercel/analytics/react'
import './globals.css'

export const metadata: Metadata = {
  title: 'Yoocal — Things To Do in Park City, Utah | Local Events Calendar',
  description: 'Find everything happening in Park City, Utah — concerts, outdoor adventures, festivals, food events, races and more. One free calendar updated daily from every local source.',
  metadataBase: new URL('https://www.yoocal.com'),
  openGraph: {
    siteName: 'Yoocal',
    images: [{ url: '/og-image.png', width: 1200, height: 630 }],
  },
  appleWebApp: { capable: true, title: 'Yoocal', statusBarStyle: 'black-translucent' },
  icons: { apple: '/icons/apple-touch-icon.png' },
}

export const viewport: Viewport = { themeColor: '#1a1830' }

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${dmSans.variable} ${dmSerif.variable}`}>
      <head>
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <link rel="sitemap" type="application/xml" href="/sitemap.xml" />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link rel="preconnect" href="https://unpkg.com" />
        <Script
          src={`https://maps.googleapis.com/maps/api/js?key=${process.env.NEXT_PUBLIC_GOOGLE_MAPS_KEY}&libraries=places&callback=initPlacesAutocomplete`}
          strategy="afterInteractive"
        />
        <Script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" strategy="afterInteractive" />
      </head>
      <body>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: '{"@context":"https://schema.org","@graph":[{"@type":"Organization","@id":"https://www.yoocal.com/#org","name":"Yoocal","url":"https://www.yoocal.com","logo":"https://www.yoocal.com/icons/icon-512.png","description":"Local events for scenic resort towns — one free calendar updated daily."},{"@type":"WebSite","@id":"https://www.yoocal.com/#website","url":"https://www.yoocal.com","name":"Yoocal","publisher":{"@id":"https://www.yoocal.com/#org"}}]}' }}
        />
        <ServiceWorkerRegister /><MetaPixel />{children}<Analytics />
      </body>
    </html>
  )
}
