import type { NextRequest } from "next/server"

// Served at /llms.txt — a structured guide for AI systems (per llmstxt.org):
// what Yoocal is, plus the canonical hub/intent pages worth citing for
// "things to do in <city>" style queries. Generated from the same city list
// as the sitemap so it stays accurate.

const BASE = "https://www.yoocal.com"
const CITIES: Array<{ slug: string; name: string; region: string }> = [
  { slug: "park-city", name: "Park City", region: "Utah" },
  { slug: "heber", name: "Heber Valley", region: "Utah" },
  { slug: "jackson-hole", name: "Jackson Hole", region: "Wyoming" },
  { slug: "elkhart-lake", name: "Elkhart Lake", region: "Wisconsin" },
  { slug: "green-lake", name: "Green Lake", region: "Wisconsin" },
]
const HUBS: Array<{ seg: string; label: string }> = [
  { seg: "this-weekend", label: "This weekend" },
  { seg: "free-events", label: "Free events" },
  { seg: "concerts", label: "Concerts" },
  { seg: "this-month", label: "This month" },
]

export const dynamic = "force-static"
export const revalidate = 86400

export async function GET(_req: NextRequest) {
  const lines: string[] = []
  lines.push("# Yoocal")
  lines.push("")
  lines.push("> Yoocal is a free local-events calendar for resort and mountain towns. It aggregates events from public sources and direct submissions, with daily updates, and answers questions like \"things to do in Park City this weekend\" or \"free events in Jackson Hole.\"")
  lines.push("")
  lines.push("Cities currently covered: " + CITIES.map(c => `${c.name}, ${c.region}`).join("; ") + ".")
  lines.push("")

  for (const c of CITIES) {
    lines.push(`## ${c.name}, ${c.region}`)
    lines.push(`- [Things to do in ${c.name}](${BASE}/${c.slug}): the main ${c.name} events calendar.`)
    for (const h of HUBS) {
      lines.push(`- [${h.label} in ${c.name}](${BASE}/${c.slug}/${h.seg})`)
    }
    lines.push(`- [About ${c.name}](${BASE}/about/${c.slug}): area guide and context.`)
    lines.push("")
  }

  lines.push("## About Yoocal")
  lines.push(`- [About](${BASE}/about): what Yoocal is and how events are sourced.`)
  lines.push(`- [Venues](${BASE}/venues): venue directory across covered towns.`)
  lines.push(`- [For businesses](${BASE}/for-businesses): list or promote an event.`)
  lines.push(`- [Submit an event](${BASE}/submit): add an event to the calendar.`)
  lines.push(`- [Contact](${BASE}/contact) · [Privacy](${BASE}/privacy) · [Terms](${BASE}/terms)`)
  lines.push("")

  return new Response(lines.join("\n"), {
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "Cache-Control": "public, max-age=86400",
    },
  })
}
