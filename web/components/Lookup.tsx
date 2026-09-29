"use client";

import { useState } from "react";
import { countryToFlag } from "@/lib/util";

type LookupResult = {
  title?: string;
  year?: number;
  offers?: Record<string, string[]>;
  error?: string;
};

export default function Lookup({ countries }: { countries: string[] }) {
  const [query, setQuery] = useState("");
  const [year, setYear] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<LookupResult | null>(null);

  async function search(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setResult(null);
    try {
      const params = new URLSearchParams({ q: query.trim(), countries: countries.join(",") });
      if (year) params.set("year", year);
      const res = await fetch(`/api/lookup?${params}`);
      setResult(await res.json());
    } catch {
      setResult({ error: "Lookup failed. Try again." });
    } finally {
      setLoading(false);
    }
  }

  const entries = Object.entries(result?.offers ?? {}).sort(([a], [b]) => a.localeCompare(b));

  return (
    <div className="max-w-2xl">
      <form onSubmit={search} className="flex gap-3">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Type a movie name…"
          className="min-w-0 flex-1 rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm outline-none placeholder:text-white/40 focus:border-indigo-400"
        />
        <input
          value={year}
          onChange={(e) => setYear(e.target.value.replace(/\D/g, "").slice(0, 4))}
          placeholder="Year"
          inputMode="numeric"
          className="w-24 rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm outline-none placeholder:text-white/40 focus:border-indigo-400"
        />
        <button
          type="submit"
          disabled={loading}
          className="rounded-full bg-indigo-500 px-5 py-2 text-sm font-medium hover:bg-indigo-400 disabled:opacity-50"
        >
          {loading ? "Searching…" : "Search"}
        </button>
      </form>

      <div className="mt-6">
        {result?.error && <p className="text-white/60">{result.error}</p>}
        {result?.title && (
          <>
            <h2 className="text-xl font-semibold">
              {result.title} {result.year ? `(${result.year})` : ""}
            </h2>
            {entries.length === 0 ? (
              <p className="mt-3 text-white/60">No streaming offers found in your countries.</p>
            ) : (
              <div className="mt-4 space-y-3">
                {entries.map(([country, providers]) => (
                  <div key={country}>
                    <div className="text-sm font-semibold">{countryToFlag(country)} {country}</div>
                    <div className="mt-1 flex flex-wrap gap-1">
                      {providers.map((p) => (
                        <span key={p} className="rounded-full border border-indigo-400/30 bg-indigo-500/15 px-2 py-0.5 text-xs">
                          {p}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
