export type Offer = { c: string; p: string };

export type Movie = {
  title: string;
  year: number | null;
  poster: string | null;
  runtime: number | null;
  offers: Offer[];
  sources: string[];
};

export type SiteData = {
  lastUpdated: string;
  scanCountries: string[];
  movies: Movie[];
};

// Chip label -> provider names that count as "owned"
export const OWNED_SERVICES: Record<string, string[]> = {
  Netflix: ["Netflix"],
  Prime: ["Amazon Prime Video"],
  HBO: ["HBO Max"],
  Apple: ["Apple TV"],
  Disney: ["Disney Plus"],
  Youtube: ["YouTube"],
  RTVE: ["RTVE"],
  Filmin: ["Filmin"],
};
