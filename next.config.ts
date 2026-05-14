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
}

export default nextConfig
