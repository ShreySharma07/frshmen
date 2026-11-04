// How many Gemini fit checks are left today, as a ring that empties as they're used.
export function FitRing({ remaining, limit }: { remaining: number; limit: number }) {
  const r = 26, c = 2 * Math.PI * r;
  const share = limit ? remaining / limit : 0;
  return (
    <svg viewBox="0 0 64 64" className="size-16 shrink-0" role="img" aria-label={`${remaining} of ${limit} fit checks left today`}>
      <circle cx="32" cy="32" r={r} fill="none" strokeWidth="6" className="stroke-surface" />
      <circle cx="32" cy="32" r={r} fill="none" strokeWidth="6" strokeLinecap="round" className="stroke-accent"
        strokeDasharray={`${share * c} ${c}`} transform="rotate(-90 32 32)" />
      <text x="32" y="37" textAnchor="middle" className="fill-ink font-mono text-[15px] font-semibold">{remaining}</text>
    </svg>
  );
}
