export function countryToFlag(code: string): string {
  let c = code.toUpperCase();
  if (c === "UK") c = "GB";
  if (c.length !== 2) return c;
  return String.fromCodePoint(...[...c].map((ch) => ch.charCodeAt(0) + 127397));
}

export function formatRuntime(mins: number | null): string {
  if (mins == null) return "";
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return h ? `${h}h ${m}m` : `${m}m`;
}
