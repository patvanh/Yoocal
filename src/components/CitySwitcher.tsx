"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";

/**
 * City switcher pill tabs. Updates the ?city= query param without a full
 * page reload (server component above re-fetches via the URL change).
 */
export default function CitySwitcher({
  active,
}: {
  active: "parkcity" | "elkhartlake";
}) {
  const router = useRouter();
  const params = useSearchParams();
  const pathname = usePathname();

  function switchTo(city: "parkcity" | "elkhartlake") {
    if (city === active) return;
    const sp = new URLSearchParams(params.toString());
    sp.set("city", city);
    router.push(`${pathname}?${sp.toString()}`);
  }

  const tabs: { key: "parkcity" | "elkhartlake"; label: string; emoji: string }[] = [
    { key: "parkcity", label: "Park City", emoji: "⛷️" },
    { key: "elkhartlake", label: "Elkhart Lake", emoji: "🏁" },
  ];

  return (
    <>
      <div className="yc-city-tabs" role="tablist">
        {tabs.map((t) => (
          <button
            key={t.key}
            role="tab"
            aria-selected={active === t.key}
            className={active === t.key ? "active" : ""}
            onClick={() => switchTo(t.key)}
          >
            <span className="emoji">{t.emoji}</span>
            {t.label}
          </button>
        ))}
      </div>

      <style>{`
        .yc-city-tabs {
          display: inline-flex;
          gap: 6px;
          padding: 6px;
          background: rgba(255,255,255,0.08);
          border: 1px solid rgba(255,255,255,0.12);
          border-radius: 100px;
          margin-top: 24px;
        }
        .yc-city-tabs button {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          padding: 8px 18px;
          font-size: 14px;
          font-weight: 600;
          color: rgba(255,255,255,0.7);
          background: transparent;
          border: none;
          border-radius: 100px;
          cursor: pointer;
          font-family: inherit;
          transition: all 0.2s;
        }
        .yc-city-tabs button:hover {
          color: white;
        }
        .yc-city-tabs button.active {
          background: var(--purple, #534AB7);
          color: white;
        }
        .yc-city-tabs .emoji {
          font-size: 16px;
        }
      `}</style>
    </>
  );
}
