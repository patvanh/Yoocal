"use client"

import { useEffect } from "react"
import { usePathname } from "next/navigation"
import Script from "next/script"

const PIXEL_ID = process.env.NEXT_PUBLIC_META_PIXEL_ID

/**
 * MetaPixel — loads the Meta (Facebook) Pixel and fires PageView on every
 * route change. Next's client-side navigation doesn't trigger a fresh page
 * load, so PageView must be re-fired on pathname change or in-app navigations
 * (e.g. clicking from the homepage to a city page) would go uncounted, which
 * undercounts traffic and breaks retargeting. No-op if the env var is unset,
 * so local/dev builds without a pixel ID are unaffected.
 */
export default function MetaPixel() {
  const pathname = usePathname()

  // Known city slugs — used to fire a CityView custom event so ad reporting
  // can break engaged visits down by city.
  const CITY_SLUGS = ['park-city', 'jackson-hole', 'heber', 'elkhart-lake', 'green-lake']

  // Fire PageView on each client-side navigation (the initial PageView is
  // fired in the init script below). Also fire a CityView custom event when
  // the visitor lands on a city hub page (e.g. /park-city), so Meta reporting
  // shows which cities the ads actually drive visits to.
  useEffect(() => {
    if (!PIXEL_ID) return
    if (typeof window === "undefined") return
    const fbq = (window as any).fbq
    if (typeof fbq !== "function") return
    fbq("track", "PageView")
    const seg = (pathname || "").split("/").filter(Boolean)
    if (seg.length === 1 && CITY_SLUGS.includes(seg[0])) {
      fbq("trackCustom", "CityView", { city: seg[0] })
    }
  }, [pathname])

  if (!PIXEL_ID) return null

  return (
    <>
      <Script id="meta-pixel" strategy="lazyOnload">
        {`
          !function(f,b,e,v,n,t,s)
          {if(f.fbq)return;n=f.fbq=function(){n.callMethod?
          n.callMethod.apply(n,arguments):n.queue.push(arguments)};
          if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';
          n.queue=[];t=b.createElement(e);t.async=!0;
          t.src=v;s=b.getElementsByTagName(e)[0];
          s.parentNode.insertBefore(t,s)}(window, document,'script',
          'https://connect.facebook.net/en_US/fbevents.js');
          fbq('init', '${PIXEL_ID}');
          fbq('track', 'PageView');
        `}
      </Script>
      <noscript>
        <img
          height="1"
          width="1"
          style={{ display: "none" }}
          alt=""
          src={`https://www.facebook.com/tr?id=${PIXEL_ID}&ev=PageView&noscript=1`}
        />
      </noscript>
    </>
  )
}
