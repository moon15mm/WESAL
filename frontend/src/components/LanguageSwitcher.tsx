"use client";

import * as DM from "@radix-ui/react-dropdown-menu";
import { Check, Globe } from "lucide-react";
import { useLocale } from "next-intl";
import { useSearchParams } from "next/navigation";
import { usePathname, useRouter } from "@/i18n/navigation";
import { localeNames, locales, type Locale } from "@/i18n/routing";
import { api } from "@/lib/api";
import { cx } from "@/lib/format";
import { useSession } from "@/lib/session";

export function LanguageSwitcher({ inverse = false, compact = false }: { inverse?: boolean; compact?: boolean }) {
  const locale = useLocale();
  const router = useRouter();
  const pathname = usePathname();
  const search = useSearchParams();
  const { me, refresh } = useSession();

  async function change(l: Locale) {
    if (me) {
      try {
        await api("/auth/me", { method: "PATCH", body: { locale: l } });
        await refresh();
      } catch {
        /* the UI language still changes */
      }
    }
    const qs = search.toString();
    router.replace(`${pathname}${qs ? `?${qs}` : ""}`, { locale: l });
  }

  return (
    <DM.Root>
      <DM.Trigger asChild>
        <button
          className={cx(
            "inline-flex h-9 items-center gap-1.5 rounded-md px-2.5 text-sm font-medium transition",
            inverse ? "text-white/90 hover:bg-white/10" : "text-ink hover:bg-navy-50",
          )}
          aria-label="Language"
          data-testid="language-switcher"
        >
          <Globe className="h-4 w-4" />
          {!compact && <span>{localeNames[locale as Locale]}</span>}
        </button>
      </DM.Trigger>
      <DM.Portal>
        <DM.Content sideOffset={6} align="end" className="z-50 min-w-40 rounded-md border border-line bg-white p-1 shadow-[var(--shadow-pop)]">
          {locales.map((l) => (
            <DM.Item
              key={l}
              onSelect={() => change(l)}
              className="flex cursor-pointer items-center justify-between gap-4 rounded-sm px-3 py-2 text-sm outline-none data-[highlighted]:bg-navy-50"
              lang={l}
              data-testid={`lang-${l}`}
            >
              <span>{localeNames[l]}</span>
              {l === locale && <Check className="h-4 w-4 text-teal-500" />}
            </DM.Item>
          ))}
        </DM.Content>
      </DM.Portal>
    </DM.Root>
  );
}
