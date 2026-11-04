import { getTranslations, setRequestLocale } from "next-intl/server";
import { notFound } from "next/navigation";
import { SiteFooter, SiteHeader } from "@/components/marketing/SiteChrome";
import { Markdown } from "@/lib/markdown";

const API_INTERNAL = process.env.API_INTERNAL_URL || "http://localhost:8000";
const SLUGS = ["terms", "privacy", "supplier-agreement", "representative-agreement", "commission-policy", "complaints-policy", "returns-policy", "ratings-policy", "data-use-policy", "data-retention-policy"];

type PageData = { slug: string; locale: string; title: string; body: string; version: string; updated_at: string };

async function load(slug: string, locale: string): Promise<PageData | null> {
  try {
    const res = await fetch(`${API_INTERNAL}/api/v1/public/pages/${slug}`, { headers: { "x-locale": locale }, next: { revalidate: 300 } });
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

export async function generateMetadata({ params }: { params: Promise<{ locale: string; slug: string }> }) {
  const { locale, slug } = await params;
  const t = await getTranslations({ locale, namespace: "marketing" });
  return { title: SLUGS.includes(slug) ? t(`legal.${slug}`) : "" };
}

export default async function LegalPage({ params }: { params: Promise<{ locale: string; slug: string }> }) {
  const { locale, slug } = await params;
  setRequestLocale(locale);
  if (!SLUGS.includes(slug)) notFound();
  const t = await getTranslations("marketing");
  const page = await load(slug, locale);
  return (
    <>
      <SiteHeader />
      <main className="mx-auto max-w-3xl px-4 py-12 sm:px-6">
        {page ? (
          <article>
            {page.locale !== locale && <p className="mb-6 rounded-md bg-warning/10 p-3 text-sm text-[#8a5c19]">{t("legal_language_note")}</p>}
            <div dir={page.locale === "ar" || page.locale === "ur" ? "rtl" : "ltr"}><Markdown source={page.body} /></div>
            <p className="mt-10 text-xs text-muted">{t("legal_version", { version: page.version })}</p>
          </article>
        ) : (
          <p className="text-muted">{t("legal_unavailable")}</p>
        )}
      </main>
      <SiteFooter />
    </>
  );
}
