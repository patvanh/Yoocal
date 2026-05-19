"use client"

import { useEffect, useState } from "react"
import { useSearchParams } from "next/navigation"
import CalendarClient from "@/components/CalendarClient"
import HomeBrand from "@/components/HomeBrand"

/**
 * Bare / always renders the brand homepage. ?city=foo renders the calendar
 * for that city. No localStorage-based redirects — the bare root is always
 * brand for every visitor.
 */
export default function HomeRouter() {
  const params = useSearchParams()
  const [view, setView] = useState<"loading" | "brand" | "calendar">("loading")

  useEffect(() => {
    const cityParam = params.get("city")
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
  if (view === "calendar") return <CalendarClient />
  return <HomeBrand />
}
