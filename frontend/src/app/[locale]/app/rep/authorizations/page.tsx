"use client";

import { useTranslations } from "next-intl";
import { AuthorizationTable, type Authorization } from "@/components/app/authorizations";
import { Card, PageHeader } from "@/components/ui/layout";
import { Link } from "@/i18n/navigation";
import { useApiQuery } from "@/lib/list";

export default function RepAuthorizations() {
  const t = useTranslations("authorizations");
  const q = useApiQuery<Authorization[]>(["rep-auths"], "/rep/authorizations");
  return (
    <>
      <PageHeader title={t("title")} subtitle={t("rep_subtitle")} actions={<Link href="/app/rep/companies" className="inline-flex h-10 items-center rounded-md bg-teal-500 px-4 text-sm font-semibold text-white">{t("request_new")}</Link>} />
      <Card padded={false}><AuthorizationTable rows={q.data} loading={q.isLoading} side="rep" /></Card>
    </>
  );
}
