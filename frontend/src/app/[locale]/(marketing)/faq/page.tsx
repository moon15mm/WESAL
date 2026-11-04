import { getTranslations, setRequestLocale } from "next-intl/server";
import { SiteFooter, SiteHeader } from "@/components/marketing/SiteChrome";

const KEYS = ["what", "payments", "delivery", "reps_any_company", "approval", "fees", "data", "languages"];

export default async function FaqPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("marketing");
  return (
    <>
      <SiteHeader />
      <main className="mx-auto max-w-3xl px-4 py-14 sm:px-6">
        <h1 className="text-3xl font-bold text-navy-700">{t("faq_title")}</h1>
        <div className="mt-8 divide-y divide-line rounded-xl border border-line bg-white">
          {KEYS.map((k) => (
            <details key={k} className="group p-5" open={k === "what"}>
              <summary className="cursor-pointer font-medium text-navy-700">{t(`faq.${k}_q`)}</summary>
              <p className="mt-3 text-sm leading-7 text-muted">{t(`faq.${k}_a`)}</p>
            </details>
          ))}
        </div>
      </main>
      <SiteFooter />
    </>
  );
}
