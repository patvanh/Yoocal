"use client"

import { useEffect, useState } from "react"
import { useSearchParams, useRouter } from "next/navigation"
import CalendarClient from "@/components/CalendarClient"
import HomeBrand from "@/components/HomeBrand"

/**
 * Decides which homepage view to render:
 *  - If ?city=... is in the URL, show the calendar.
 *  - Else if a returning visitor has yoocal.lastCity in localStorage, redirect
 *    to that city so they skip the brand page.
 *  - Else show the brand landing page (city picker + search).
 */
export default function HomeRouter() {
  const params = useSearchParams()
  const router = useRouter()
  const [view, setView] = useState<"loading" | "brand" | "calendar">("loading")

  useEffect(() => {
    // Server-rendered query param has priority
    const cityParam = params.get("city")
    if (cityParam) {
      setView("calendar")
      return
    }
    // Returning-visitor shortcut
    try {
      const last =
        typeof window !== "undefined"
          ? window.localStorage.getItem("yoocal.lastCity")
          : null
      if (last) {
        router.replace(`/?city=${last}`)
        return
      }
    } catch {
      // localStorage blocked — fall through to brand view
    }
    setView("brand")
  }, [params, router])

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
  if (view === "calendar") return <CalendarClient />
  return <HomeBrand />
}
