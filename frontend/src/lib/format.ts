"use client";

import { useLocale } from "next-intl";
import { useMemo } from "react";
import { useSession } from "./session";

const NATIVE: Record<string, string> = { ar: "arab", ur: "arabext", hi: "deva", en: "latn" };

export function useFormat() {
  const locale = useLocale();
  const { me } = useSession();
  const nu = me?.number_system === "arab" ? NATIVE[locale] || "latn" : "latn";
  const tz = me?.timezone || "Asia/Riyadh";
  const currency = me?.currency || "SAR";
  const tag = `${locale === "ar" ? "ar-SA" : locale === "ur" ? "ur-PK" : locale === "hi" ? "hi-IN" : "en-GB"}-u-nu-${nu}`;
  return useMemo(() => {
    const num = new Intl.NumberFormat(tag, { maximumFractionDigits: 2 });
    const moneyF = new Intl.NumberFormat(tag, { style: "currency", currency, minimumFractionDigits: 2, maximumFractionDigits: 2 });
    const dateF = new Intl.DateTimeFormat(tag, { dateStyle: "medium", timeZone: tz });
    const dtF = new Intl.DateTimeFormat(tag, { dateStyle: "medium", timeStyle: "short", timeZone: tz });
    const rel = new Intl.RelativeTimeFormat(tag, { numeric: "auto" });
    const toNum = (v: unknown) => (v === null || v === undefined || v === "" ? NaN : Number(v));
    return {
      number: (v: unknown) => (isNaN(toNum(v)) ? "—" : num.format(toNum(v))),
      money: (v: unknown) => (isNaN(toNum(v)) ? "—" : moneyF.format(toNum(v))),
      percent: (v: unknown) => (isNaN(toNum(v)) ? "—" : `${num.format(toNum(v))}%`),
      date: (v: unknown) => (v ? dateF.format(new Date(String(v))) : "—"),
      datetime: (v: unknown) => (v ? dtF.format(new Date(String(v))) : "—"),
      relative: (v: unknown) => {
        if (!v) return "—";
        const diff = (new Date(String(v)).getTime() - Date.now()) / 1000;
        const abs = Math.abs(diff);
        if (abs < 60) return rel.format(Math.round(diff), "second");
        if (abs < 3600) return rel.format(Math.round(diff / 60), "minute");
        if (abs < 86400) return rel.format(Math.round(diff / 3600), "hour");
        return rel.format(Math.round(diff / 86400), "day");
      },
    };
  }, [tag, tz, currency]);
}

export function cx(...parts: (string | false | null | undefined)[]) {
  return parts.filter(Boolean).join(" ");
}
