"use client";

import { useMemo, useState } from "react";
import { OWNED_SERVICES, type Movie, type SiteData } from "@/lib/types";
import { countryToFlag, formatRuntime } from "@/lib/util";

type Sort = "runtime-asc" | "runtime-desc" | "title" | "year-desc" | "year-asc";

const SORTS: { value: Sort; label: string }[] = [
  { value: "runtime-asc", label: "Runtime ↑" },
  { value: "runtime-desc", label: "Runtime ↓" },
  { value: "title", label: "Title A-Z" },
  { value: "year-desc", label: "Year ↓" },
  { value: "year-asc", label: "Year ↑" },
];

function toggle<T>(set: Set<T>, value: T): Set<T> {
  const next = new Set(set);
  if (next.has(value)) next.delete(value);
  else next.add(value);
  return next;
}

function Chip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`rounded-full border px-3 py-1 text-xs transition-colors ${
        active
          ? "border-indigo-400 bg-indigo-500/20 text-indigo-100"
          : "border-white/10 text-white/60 hover:border-white/30 hover:text-white"
      }`}
    >
      {children}
    </button>
  );
}

// Collapsible filter section with Select all / Clear
function FilterGroup({
  title,
  selected,
  total,
  onAll,
  onNone,
  scroll,
  children,
}: {
  title: string;
  selected: number;
  total: number;
  onAll: () => void;
  onNone: () => void;
  scroll?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-lg border border-white/10">
      <button
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className="flex w-full items-center justify-between px-3 py-2 text-sm"
      >
        <span>{title}</span>
        <span className="flex items-center gap-2 text-xs text-white/50">
          {selected}/{total}
          <span className={`transition-transform ${open ? "rotate-180" : ""}`}>▾</span>
        </span>
      </button>
      {open && (
        <div className="border-t border-white/10 px-3 py-3">
          <div className="mb-2 flex gap-3 text-xs">
            <button onClick={onAll} className="text-indigo-300 hover:underline">Select all</button>
            <button onClick={onNone} className="text-white/50 hover:underline">Clear</button>
          </div>
          <div className={`flex flex-wrap gap-2 ${scroll ? "max-h-56 overflow-y-auto pr-1" : ""}`}>
            {children}
          </div>
        </div>
      )}
    </div>
  );
}

export default function Watchlist({ data }: { data: SiteData }) {
  const allCountries = useMemo(
    () => [...new Set(data.movies.flatMap((m) => m.offers.map((o) => o.c)))].sort(),
    [data],
  );
  const allSources = useMemo(
    () => [...new Set(data.movies.flatMap((m) => m.sources))].sort(),
    [data],
  );
  const ownedLabels = Object.keys(OWNED_SERVICES);

  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<Sort>("runtime-asc");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [countries, setCountries] = useState<Set<string>>(new Set(allCountries));
  const [sources, setSources] = useState<Set<string>>(
    new Set(allSources.filter((s) => s !== "Alyssa")),
  );
  // Owned chips only restrict results while at least one is on
  const [owned, setOwned] = useState<Set<string>>(new Set(ownedLabels));
  // Excluded (not selected) so providers that appear later default to included
  const [excludedProviders, setExcludedProviders] = useState<Set<string>>(new Set());

  const ownedProviders = useMemo(
    () => new Set([...owned].flatMap((label) => OWNED_SERVICES[label])),
    [owned],
  );

  // Providers available in the currently selected countries
  const providers = useMemo(
    () =>
      [...new Set(
        data.movies.flatMap((m) => m.offers.filter((o) => countries.has(o.c)).map((o) => o.p)),
      )].sort(),
    [data, countries],
  );

  const movies = useMemo(() => {
    const q = query.trim().toLowerCase();
    const result = data.movies
      .filter((m) => !q || m.title.toLowerCase().includes(q))
      .filter((m) => m.sources.some((s) => sources.has(s)))
      .map((m) => ({
        ...m,
        offers: m.offers.filter(
          (o) =>
            countries.has(o.c) &&
            !excludedProviders.has(o.p) &&
            (owned.size === 0 || ownedProviders.has(o.p)),
        ),
      }))
      .filter((m) => m.offers.length > 0);

    const byNum = (a: number | null, b: number | null, dir: 1 | -1) =>
      a == null ? 1 : b == null ? -1 : (a - b) * dir;
    result.sort((a, b) => {
      switch (sort) {
        case "runtime-asc": return byNum(a.runtime, b.runtime, 1);
        case "runtime-desc": return byNum(a.runtime, b.runtime, -1);
        case "year-desc": return byNum(a.year, b.year, -1);
        case "year-asc": return byNum(a.year, b.year, 1);
        default: return a.title.localeCompare(b.title);
      }
    });
    return result;
  }, [data, query, sort, countries, excludedProviders, owned, ownedProviders, sources]);

  const stats = useMemo(() => {
    const c = new Set<string>();
    const p = new Set<string>();
    movies.forEach((m) => m.offers.forEach((o) => { c.add(o.c); p.add(o.p); }));
    return { countries: c.size, providers: p.size };
  }, [movies]);

  const selectedProviders = providers.filter((p) => !excludedProviders.has(p)).length;
  const activeFilters =
    (countries.size < allCountries.length ? 1 : 0) +
    (selectedProviders < providers.length ? 1 : 0) +
    (owned.size > 0 ? 1 : 0) +
    (sources.size < allSources.length ? 1 : 0);

  return (
    <div>
      <div className="sticky top-0 z-10 -mx-4 space-y-3 border-b border-white/10 bg-neutral-950/85 px-4 py-4 backdrop-blur">
        <div className="flex flex-wrap items-center gap-3">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search titles…"
            className="min-w-0 flex-1 rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm outline-none placeholder:text-white/40 focus:border-indigo-400"
          />
          <select
            value={sort}
            onChange={(e) => setSort(e.target.value as Sort)}
            className="rounded-full border border-white/10 bg-neutral-900 px-3 py-2 text-sm outline-none"
          >
            {SORTS.map((s) => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </select>
          <button
            onClick={() => setFiltersOpen(!filtersOpen)}
            aria-expanded={filtersOpen}
            className={`flex items-center gap-2 rounded-full border px-4 py-2 text-sm ${
              filtersOpen ? "border-indigo-400 bg-indigo-500/20" : "border-white/10 hover:border-white/30"
            }`}
          >
            Filters
            {activeFilters > 0 && (
              <span className="rounded-full bg-indigo-500 px-1.5 text-[11px]">{activeFilters}</span>
            )}
            <span className={`transition-transform ${filtersOpen ? "rotate-180" : ""}`}>▾</span>
          </button>
        </div>

        {filtersOpen && (
          <div className="grid max-h-[60vh] gap-2 overflow-y-auto sm:grid-cols-2">
            <FilterGroup
              title="🌍 Countries"
              selected={countries.size}
              total={allCountries.length}
              onAll={() => setCountries(new Set(allCountries))}
              onNone={() => setCountries(new Set())}
            >
              {allCountries.map((c) => (
                <Chip key={c} active={countries.has(c)} onClick={() => setCountries(toggle(countries, c))}>
                  {countryToFlag(c)} {c}
                </Chip>
              ))}
            </FilterGroup>

            <FilterGroup
              title="📺 Streaming services"
              selected={selectedProviders}
              total={providers.length}
              onAll={() => setExcludedProviders(new Set())}
              onNone={() => setExcludedProviders(new Set(providers))}
              scroll
            >
              {providers.map((p) => (
                <Chip
                  key={p}
                  active={!excludedProviders.has(p)}
                  onClick={() => setExcludedProviders(toggle(excludedProviders, p))}
                >
                  {p}
                </Chip>
              ))}
            </FilterGroup>

            <FilterGroup
              title="🏠 Services I own (only show these)"
              selected={owned.size}
              total={ownedLabels.length}
              onAll={() => setOwned(new Set(ownedLabels))}
              onNone={() => setOwned(new Set())}
            >
              {ownedLabels.map((s) => (
                <Chip key={s} active={owned.has(s)} onClick={() => setOwned(toggle(owned, s))}>
                  {s}
                </Chip>
              ))}
            </FilterGroup>

            <FilterGroup
              title="📋 Lists"
              selected={sources.size}
              total={allSources.length}
              onAll={() => setSources(new Set(allSources))}
              onNone={() => setSources(new Set())}
            >
              {allSources.map((s) => (
                <Chip key={s} active={sources.has(s)} onClick={() => setSources(toggle(sources, s))}>
                  {s}
                </Chip>
              ))}
            </FilterGroup>
          </div>
        )}
      </div>

      <div className="flex gap-8 py-5">
        <Stat value={movies.length} label="Movies" />
        <Stat value={stats.countries} label="Countries" />
        <Stat value={stats.providers} label="Providers" />
      </div>

      {movies.length === 0 ? (
        <p className="py-16 text-center text-white/50">No movies match your filters.</p>
      ) : (
        <div className="grid grid-cols-2 gap-x-4 gap-y-6 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
          {movies.map((m) => (
            <MovieCard key={`${m.title}-${m.year}`} movie={m} />
          ))}
        </div>
      )}
    </div>
  );
}

function Stat({ value, label }: { value: number; label: string }) {
  return (
    <div>
      <div className="text-2xl font-bold text-indigo-400">{value}</div>
      <div className="text-[11px] uppercase tracking-wider text-white/50">{label}</div>
    </div>
  );
}

function MovieCard({ movie }: { movie: Movie }) {
  const byCountry = useMemo(() => {
    const map = new Map<string, Set<string>>();
    movie.offers.forEach((o) => {
      if (!map.has(o.c)) map.set(o.c, new Set());
      map.get(o.c)!.add(o.p);
    });
    return [...map.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [movie]);

  return (
    <article className="group">
      <div className="overflow-hidden rounded-lg bg-white/5">
        {movie.poster ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={movie.poster}
            alt={movie.title}
            loading="lazy"
            className="aspect-[2/3] w-full object-cover transition-transform duration-200 group-hover:scale-[1.03]"
          />
        ) : (
          <div className="aspect-[2/3]" />
        )}
      </div>
      <h3 className="mt-2 text-sm font-semibold leading-tight">{movie.title}</h3>
      <p className="text-xs text-white/50">
        {[movie.year, formatRuntime(movie.runtime)].filter(Boolean).join(" · ")}
      </p>
      <details className="mt-1.5 rounded-md border border-white/10 text-xs">
        <summary className="cursor-pointer px-2 py-1.5 text-white/70 hover:text-white">
          📍 {byCountry.length} countries · {movie.offers.length} offers
        </summary>
        <div className="space-y-2 px-2 pb-2">
          {byCountry.map(([country, providers]) => (
            <div key={country}>
              <div className="font-semibold">{countryToFlag(country)} {country}</div>
              <div className="mt-1 flex flex-wrap gap-1">
                {[...providers].sort().map((p) => (
                  <span key={p} className="rounded-full border border-indigo-400/30 bg-indigo-500/15 px-2 py-0.5 text-[11px]">
                    {p}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </details>
    </article>
  );
}
