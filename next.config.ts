import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  // Allow images from external sources
  images: {
    remotePatterns: [
      { protocol: 'https', hostname: '*.googleapis.com' },
      { protocol: 'https', hostname: '*.openstreetmap.org' },
    ],
  },
  // Trailing slash for cleaner URLs
  trailingSlash: false,
  // Security headers. CSP is intentionally omitted here — a strict policy
  // can break Google Maps, analytics, fonts, and remote images on the live
  // site, so it warrants its own careful pass (report-only first).
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          { key: 'Strict-Transport-Security', value: 'max-age=63072000; includeSubDomains; preload' },
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'X-Frame-Options', value: 'SAMEORIGIN' },
          { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
          { key: 'Permissions-Policy', value: 'camera=(), microphone=(), payment=()' },
        ],
      },
      {
        // Long-cache static images/fonts in /public (NOT the nightly-changing
        // events-*.json data files, which must stay fresh).
        source: '/:path*.(webp|jpg|jpeg|png|svg|ico|woff|woff2)',
        headers: [
          { key: 'Cache-Control', value: 'public, max-age=31536000, immutable' },
        ],
      },
    ]
  },
}

export default nextConfig
