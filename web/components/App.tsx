"use client";

import { useState } from "react";
import Lookup from "@/components/Lookup";
import Watchlist from "@/components/Watchlist";
import type { SiteData } from "@/lib/types";

const REFRESH_URL =
  "https://github.com/bucanero2010/letterboxd-justwatch-vpn/actions/workflows/scrape.yml";

export default function App({ data }: { data: SiteData }) {
  const [tab, setTab] = useState<"watchlist" | "lookup">("watchlist");

  return (
    <main className="mx-auto w-full max-w-7xl px-4 pb-16">
      <header className="flex flex-wrap items-end justify-between gap-3 pt-8">
        <div>
          <h1 className="text-2xl font-bold">🍿 Global Watchlist</h1>
          <p className="text-sm text-white/50">Where your watchlist is streaming worldwide</p>
        </div>
        <p className="text-xs text-white/40">
          Updated {data.lastUpdated} ·{" "}
          <a href={REFRESH_URL} className="underline hover:text-white">
            trigger refresh
          </a>
        </p>
      </header>

      <nav className="mt-6 flex gap-6 border-b border-white/10 text-sm">
        {(
          [
            ["watchlist", "🍿 Watchlist"],
            ["lookup", "🔍 Quick Lookup"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`-mb-px border-b-2 pb-3 ${
              tab === id
                ? "border-indigo-400 text-white"
                : "border-transparent text-white/50 hover:text-white"
            }`}
          >
            {label}
          </button>
        ))}
      </nav>

      <div className="pt-4">
        {/* Keep Watchlist mounted so filters survive tab switches */}
        <div hidden={tab !== "watchlist"}>
          <Watchlist data={data} />
        </div>
        {tab === "lookup" && <Lookup countries={data.scanCountries} />}
      </div>
    </main>
  );
}
