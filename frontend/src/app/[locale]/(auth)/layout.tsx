import { getTranslations } from "next-intl/server";
import { Suspense } from "react";
import { Logo } from "@/components/brand/Logo";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { Link } from "@/i18n/navigation";

export default async function AuthLayout({ children }: { children: React.ReactNode }) {
  const t = await getTranslations("auth");
  const tb = await getTranslations("brand");
  return (
    <div className="grid min-h-screen lg:grid-cols-[1fr_minmax(0,520px)]">
      <aside className="relative hidden overflow-hidden bg-navy-700 p-12 text-white lg:flex lg:flex-col lg:justify-between">
        <div className="bg-grid absolute inset-0" />
        <div className="absolute -bottom-32 -start-32 h-96 w-96 rounded-full bg-teal-500/30 blur-[100px]" />
        <Link href="/" className="relative"><Logo size={40} inverse /></Link>
        <div className="relative max-w-md">
          <h2 className="text-3xl font-bold leading-snug">{t("side_title")}</h2>
          <p className="mt-4 leading-7 text-navy-100">{t("side_text")}</p>
          <ul className="mt-8 space-y-3 text-sm text-navy-100">
            {["side_1", "side_2", "side_3"].map((k) => (
              <li key={k} className="flex items-center gap-3"><span className="h-2 w-2 rounded-full bg-teal-300" />{t(k)}</li>
            ))}
          </ul>
        </div>
        <p className="relative text-sm text-teal-300">{tb("tagline")}</p>
      </aside>
      <main className="flex flex-col bg-white">
        <div className="flex items-center justify-between p-4 sm:p-6">
          <Link href="/" className="lg:invisible"><Logo size={32} /></Link>
          <Suspense><LanguageSwitcher /></Suspense>
        </div>
        <div className="flex flex-1 items-start justify-center px-4 pb-12 pt-4 sm:px-10 sm:pt-10">
          <div className="w-full max-w-md animate-slide-up">{children}</div>
        </div>
      </main>
    </div>
  );
}
