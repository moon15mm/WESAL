import { getTranslations } from "next-intl/server";
import { Link } from "@/i18n/navigation";
import { LogoMark } from "@/components/brand/Logo";

export default async function NotFound() {
  const t = await getTranslations("common");
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 p-6 text-center">
      <LogoMark size={56} />
      <h1 className="text-3xl font-bold text-navy-700">404</h1>
      <p className="text-muted">{t("not_found")}</p>
      <Link href="/" className="rounded-md bg-navy-700 px-4 py-2 text-sm font-medium text-white">{t("back_home")}</Link>
    </main>
  );
}
