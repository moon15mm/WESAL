import { getTranslations, setRequestLocale } from "next-intl/server";
import { ContactForm } from "@/components/marketing/ContactForm";
import { SiteFooter, SiteHeader } from "@/components/marketing/SiteChrome";

export default async function ContactPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("marketing");
  return (
    <>
      <SiteHeader />
      <main className="mx-auto max-w-xl px-4 py-14 sm:px-6">
        <h1 className="text-3xl font-bold text-navy-700">{t("contact_title")}</h1>
        <p className="mt-2 text-muted">{t("contact_subtitle")}</p>
        <div className="mt-8"><ContactForm /></div>
      </main>
      <SiteFooter />
    </>
  );
}
