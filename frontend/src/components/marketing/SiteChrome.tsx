import { getTranslations } from "next-intl/server";
import { Suspense } from "react";
import { Logo } from "@/components/brand/Logo";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { Link } from "@/i18n/navigation";

export async function SiteHeader({ transparent = false }: { transparent?: boolean }) {
  const t = await getTranslations("marketing");
  const tb = await getTranslations("brand");
  const nav = [
    ["#how", t("nav_how")],
    ["#stores", t("nav_stores")],
    ["#reps", t("nav_reps")],
    ["#suppliers", t("nav_suppliers")],
    ["#faq", t("nav_faq")],
  ];
  return (
    <header className={transparent ? "absolute inset-x-0 top-0 z-30" : "sticky top-0 z-30 border-b border-line bg-white/90 backdrop-blur"}>
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-4 sm:px-6">
        <Link href="/" aria-label={tb("name")}>
          <Logo size={34} inverse={transparent} />
        </Link>
        <nav className="hidden items-center gap-1 lg:flex">
          {nav.map(([href, label]) => (
            <Link key={href} href={`/${href}`} className={`rounded-md px-3 py-2 text-sm font-medium transition ${transparent ? "text-white/85 hover:text-white" : "text-ink hover:bg-navy-50"}`}>
              {label}
            </Link>
          ))}
        </nav>
        <div className="flex items-center gap-1 sm:gap-2">
          <Suspense>
            <LanguageSwitcher inverse={transparent} compact />
          </Suspense>
          <Link href="/login" className={`hidden rounded-md px-3 py-2 text-sm font-medium sm:inline-flex ${transparent ? "text-white hover:bg-white/10" : "text-navy-700 hover:bg-navy-50"}`}>
            {t("login")}
          </Link>
          <Link href="/register" className="inline-flex h-9 items-center rounded-md bg-teal-500 px-4 text-sm font-semibold text-white shadow-sm transition hover:bg-teal-600" data-testid="cta-register">
            {t("register")}
          </Link>
        </div>
      </div>
    </header>
  );
}

export async function SiteFooter() {
  const t = await getTranslations("marketing");
  const tb = await getTranslations("brand");
  const legal = ["terms", "privacy", "supplier-agreement", "representative-agreement", "commission-policy", "complaints-policy", "returns-policy", "ratings-policy", "data-use-policy", "data-retention-policy"];
  return (
    <footer className="bg-navy-800 text-navy-100">
      <div className="mx-auto grid max-w-7xl gap-10 px-4 py-14 sm:px-6 md:grid-cols-4">
        <div className="md:col-span-2">
          <Logo size={36} inverse />
          <p className="mt-4 max-w-sm text-sm leading-7 text-navy-200">{t("footer_about")}</p>
          <p className="mt-4 text-sm font-medium text-teal-300">{tb("tagline")}</p>
        </div>
        <div>
          <h4 className="mb-3 text-sm font-semibold text-white">{t("footer_platform")}</h4>
          <ul className="space-y-2 text-sm">
            <li><Link href="/register?type=retailer" className="hover:text-white">{t("join_store")}</Link></li>
            <li><Link href="/register?type=representative" className="hover:text-white">{t("join_rep")}</Link></li>
            <li><Link href="/register?type=supplier" className="hover:text-white">{t("join_supplier")}</Link></li>
            <li><Link href="/contact" className="hover:text-white">{t("contact")}</Link></li>
            <li><Link href="/faq" className="hover:text-white">{t("nav_faq")}</Link></li>
          </ul>
        </div>
        <div>
          <h4 className="mb-3 text-sm font-semibold text-white">{t("footer_legal")}</h4>
          <ul className="space-y-2 text-sm">
            {legal.map((s) => (
              <li key={s}><Link href={`/legal/${s}`} className="hover:text-white">{t(`legal.${s}`)}</Link></li>
            ))}
          </ul>
        </div>
      </div>
      <div className="border-t border-white/10">
        <div className="mx-auto flex max-w-7xl flex-col gap-2 px-4 py-5 text-xs text-navy-200 sm:flex-row sm:justify-between sm:px-6">
          <span>© {new Date().getFullYear()} {tb("name")} — {t("rights")}</span>
          <span>{t("footer_disclaimer")}</span>
        </div>
      </div>
    </footer>
  );
}
