import { redirect } from "next/navigation";

// Legacy /this-weekend?city=KEY URL. Canonical weekend pages are now path-based
// (/[city]/this-weekend) for SEO. The ?city= param always carried a city KEY
// (parkcity/jackson/heber/elkhartlake), so map key -> slug and redirect.
const KEY_TO_SLUG: Record<string, string> = {
  parkcity: "park-city",
  elkhartlake: "elkhart-lake",
  heber: "heber",
  jackson: "jackson-hole",
};

export default async function LegacyThisWeekend(
  { searchParams }: { searchParams: Promise<{ city?: string }> },
) {
  const params = await searchParams;
  const raw = (params.city || "").trim();
  const slug = KEY_TO_SLUG[raw] || "park-city";
  redirect(`/${slug}/this-weekend`);
}
