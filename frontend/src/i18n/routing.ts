import { defineRouting } from "next-intl/routing";

export const locales = ["ar", "en", "ur", "hi"] as const;
export type Locale = (typeof locales)[number];
export const rtlLocales: Locale[] = ["ar", "ur"];
export const localeNames: Record<Locale, string> = { ar: "العربية", en: "English", ur: "اردو", hi: "हिन्दी" };
export const dirOf = (l: string) => (rtlLocales.includes(l as Locale) ? "rtl" : "ltr");

export const routing = defineRouting({
  locales,
  defaultLocale: "ar",
  localePrefix: "always",
  localeCookie: { name: "WESAL_LOCALE", maxAge: 60 * 60 * 24 * 365 },
});
