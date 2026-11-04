"use client";
// A company's mark beside its jobs (docs/decisions.md, 2026-11-04): its favicon when we know its
// domain, over a letter on a tint of its own, so neighbouring jobs from different companies look
// different even without a logo. The tint's hue comes from the name, so it never changes.
import { useState } from "react";
import { useCompanyDomain } from "@/lib/companyDomains";

function hue(name: string): number {
  let h = 0;
  for (const ch of name) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return h % 360;
}

export function CompanyMark({ company, size = "md" }: { company: string; size?: "sm" | "md" | "lg" }) {
  const domain = useCompanyDomain(company);
  const [broken, setBroken] = useState<string | null>(null); // the domain whose icon failed
  const box = size === "lg" ? "size-10 text-base" : size === "sm" ? "size-6 text-caption" : "size-8 text-body";
  return (
    <span aria-hidden style={{ "--h": hue(company) } as React.CSSProperties}
      className={`relative grid shrink-0 place-items-center overflow-hidden rounded-md font-semibold ${box}
        bg-[oklch(0.94_0.04_var(--h))] text-[oklch(0.42_0.11_var(--h))]
        dark:bg-[oklch(0.3_0.05_var(--h))] dark:text-[oklch(0.86_0.08_var(--h))]`}>
      {company.trim()[0]?.toUpperCase()}
      {domain && broken !== domain && (
        // eslint-disable-next-line @next/next/no-img-element -- a static export has no image optimiser
        <img src={`https://icons.duckduckgo.com/ip3/${domain}.ico`} alt="" loading="lazy" decoding="async"
          onError={() => setBroken(domain)}
          // Tiny or missing icons are worse than the letter.
          onLoad={(e) => { if (e.currentTarget.naturalWidth < 16) setBroken(domain); }}
          className="absolute inset-0 size-full bg-white object-contain p-1" />
      )}
    </span>
  );
}
