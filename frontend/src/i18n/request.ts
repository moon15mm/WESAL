import { hasLocale } from "next-intl";
import { getRequestConfig } from "next-intl/server";
import { routing } from "./routing";

type Messages = Record<string, unknown>;
const API_INTERNAL = process.env.API_INTERNAL_URL || "http://localhost:8000";

function setPath(target: Messages, path: string, value: string) {
  const parts = path.split(".");
  let cur: Messages = target;
  for (const p of parts.slice(0, -1)) {
    if (typeof cur[p] !== "object" || cur[p] === null) return; // only override existing keys
    cur = cur[p] as Messages;
  }
  if (typeof cur[parts.at(-1)!] === "string") cur[parts.at(-1)!] = value;
}

async function overrides(locale: string): Promise<Record<string, string>> {
  try {
    const res = await fetch(`${API_INTERNAL}/api/v1/ref/translations/${locale}`, { next: { revalidate: 300 } });
    return res.ok ? await res.json() : {};
  } catch {
    return {}; // the static bundle is always sufficient
  }
}

export default getRequestConfig(async ({ requestLocale }) => {
  const requested = await requestLocale;
  const locale = hasLocale(routing.locales, requested) ? requested : routing.defaultLocale;
  const messages = structuredClone((await import(`../../messages/${locale}.json`)).default) as Messages;
  for (const [k, v] of Object.entries(await overrides(locale))) setPath(messages, k, v);
  return { locale, messages, timeZone: "Asia/Riyadh" };
});
