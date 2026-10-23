// Where the jobs are, for the landing globe. Counts come from /api/meta at runtime; SNAPSHOT is the
// 2026-10-23 08:53 UTC run, so the page shows real numbers before (or without) the API answering.
import type { Meta } from "@/lib/api";

export interface Place {
  id: string; // also the CSS anchor name cobe exposes: --cobe-{id}
  name: string;
  lat: number;
  lng: number;
  n: number;
}

// Indian cities by their own count; abroad, one hub per country carries the country's count, so a
// marker never claims a city figure we don't have.
const CITIES: Record<string, [string, number, number]> = {
  Bengaluru: ["blr", 12.97, 77.59],
  Hyderabad: ["hyd", 17.39, 78.49],
  Pune: ["pnq", 18.52, 73.86],
  Mumbai: ["bom", 19.08, 72.88],
  Noida: ["noi", 28.54, 77.39],
  Chennai: ["maa", 13.08, 80.27],
  Gurugram: ["ggn", 28.46, 77.03],
};
const COUNTRIES: Record<string, [string, number, number]> = {
  "United States": ["us", 37.77, -122.42],
  "United Kingdom": ["uk", 51.51, -0.13],
  Germany: ["de", 52.52, 13.4],
  Canada: ["ca", 43.65, -79.38],
  Japan: ["jp", 35.68, 139.69],
  Netherlands: ["nl", 52.37, 4.9],
  Singapore: ["sg", 1.35, 103.82],
  Australia: ["au", -33.87, 151.21],
  France: ["fr", 48.86, 2.35],
};

export interface Counts {
  total: number;
  fresher: number;
  companies: number;
  india: number;
  visa: number | null; // open roles that sponsor a visa or offer relocation; null until the API says
  cities: Place[];
  abroad: Place[];
}

export const SNAPSHOT: Counts = {
  total: 23390,
  fresher: 356,
  companies: 415,
  india: 5625,
  visa: null,
  cities: place(CITIES, { Bengaluru: 3236, Hyderabad: 954, Pune: 429, Mumbai: 408, Noida: 303, Chennai: 258, Gurugram: 240 }),
  abroad: place(COUNTRIES, {
    "United States": 12599, "United Kingdom": 1204, Germany: 569, Canada: 546, Japan: 264,
    Netherlands: 252, Singapore: 250, Australia: 239, France: 213,
  }),
};

export function fromMeta(meta: Meta): Counts {
  const byCity = Object.fromEntries(meta.cities.map((c) => [c.city, c.n]));
  const byCountry = Object.fromEntries(meta.countries.map((c) => [c.country, c.n]));
  return {
    total: meta.total,
    fresher: meta.levels.fresher,
    companies: meta.last_run?.companies_ok ?? SNAPSHOT.companies,
    india: byCountry.India ?? 0,
    visa: meta.visa_or_relocation ?? null,
    cities: place(CITIES, byCity),
    abroad: place(COUNTRIES, byCountry),
  };
}

function place(table: Record<string, [string, number, number]>, counts: Record<string, number>): Place[] {
  return Object.entries(table)
    .map(([name, [id, lat, lng]]) => ({ id, name, lat, lng, n: counts[name] ?? 0 }))
    .filter((p) => p.n > 0)
    .sort((a, b) => b.n - a.n);
}

export const fmt = (n: number) => n.toLocaleString("en-IN");
