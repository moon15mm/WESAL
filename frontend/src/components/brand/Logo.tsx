/* WESAL brand mark: three market parties (store · representative · supplier) as nodes,
   joined by connection paths that form a "W" under a unifying arc – "one market, connected". */

export function LogoMark({ size = 36, variant = "color", className }: { size?: number; variant?: "color" | "mono" | "inverse"; className?: string }) {
  const bg = variant === "color" ? "#102B46" : variant === "inverse" ? "#FFFFFF" : "currentColor";
  const fg = variant === "color" ? "#20B99A" : variant === "inverse" ? "#102B46" : "#FFFFFF";
  const accent = variant === "color" ? "#55D6B0" : fg;
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" className={className} role="img" aria-label="WESAL" xmlns="http://www.w3.org/2000/svg">
      <rect width="64" height="64" rx="16" fill={bg} />
      <path d="M17 24 Q32 9 47 24" stroke={accent} strokeWidth="3" fill="none" strokeLinecap="round" opacity="0.75" />
      <path d="M17 24 Q24 41 32 45 Q40 41 47 24" stroke={fg} strokeWidth="4.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="17" cy="24" r="6" fill={accent} stroke={bg} strokeWidth="2.5" />
      <circle cx="47" cy="24" r="6" fill={accent} stroke={bg} strokeWidth="2.5" />
      <circle cx="32" cy="45" r="7" fill={fg} stroke={bg} strokeWidth="2.5" />
    </svg>
  );
}

export function Logo({ size = 36, inverse = false, showTagline = false, tagline }: { size?: number; inverse?: boolean; showTagline?: boolean; tagline?: string }) {
  return (
    <span className="inline-flex items-center gap-2.5">
      <LogoMark size={size} variant={inverse ? "inverse" : "color"} />
      <span className="flex flex-col leading-none">
        <span className={`flex items-baseline gap-2 font-bold ${inverse ? "text-white" : "text-navy-700"}`} style={{ fontSize: size * 0.56 }}>
          <span style={{ fontFamily: "'IBM Plex Sans Arabic', sans-serif" }}>وِصال</span>
          <span className={`font-semibold tracking-[0.18em] ${inverse ? "text-teal-300" : "text-teal-500"}`} style={{ fontFamily: "Inter, sans-serif", fontSize: size * 0.36 }}>
            WESAL
          </span>
        </span>
        {showTagline && tagline && <span className={`mt-1 text-[11px] ${inverse ? "text-navy-100" : "text-muted"}`}>{tagline}</span>}
      </span>
    </span>
  );
}
