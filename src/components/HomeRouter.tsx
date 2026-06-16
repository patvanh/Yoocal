"use client"

import { useEffect, useState } from "react"
import { useSearchParams, useRouter } from "next/navigation"
import CalendarClient from "@/components/CalendarClient"
import CalendarClientV2 from "@/components/CalendarClientV2"
import HomeBrand from "@/components/HomeBrand"

/**
 * Bare / always renders the brand homepage. ?city=foo renders the calendar
 * for that city. No localStorage-based redirects — the bare root is always
 * brand for every visitor.
 */
export default function HomeRouter() {
  const params = useSearchParams()
  const router = useRouter()
  const [view, setView] = useState<"loading" | "brand" | "calendar">("loading")

  // Map legacy ?city= keys to clean URL slugs.
  const CITY_SLUG: Record<string, string> = {
    parkcity: "park-city",
    elkhartlake: "elkhart-lake",
    heber: "heber",
    jackson: "jackson-hole",
    greenlake: "green-lake",
  }

  useEffect(() => {
    const cityParam = params.get("city")
    if (cityParam) {
      // Redirect old ?city= URLs to the canonical clean path for SEO.
      const slug = CITY_SLUG[cityParam]
      if (slug) {
        router.replace(`/${slug}`)
        return
      }
    }
    setView(cityParam ? "calendar" : "brand")
  }, [params])

  if (view === "loading") {
    return (
      <div
        style={{
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#0e0a26",
          color: "rgba(255,255,255,0.5)",
          fontFamily: "DM Sans, sans-serif",
        }}
      >
        Loading…
      </div>
    )
  }
  if (view === "calendar") {
    const isV2 = params.get("v") === "2"
    return isV2 ? <CalendarClientV2 /> : <CalendarClient />
  }
  return <HomeBrand />
}
