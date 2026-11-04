"use client";

import { Plus } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { AuthorizationTable, type Authorization } from "@/components/app/authorizations";
import { Tabs } from "@/components/ui/data";
import { Card, PageHeader } from "@/components/ui/layout";
import { Link } from "@/i18n/navigation";
import { useApiQuery } from "@/lib/list";

export default function SupplierAuthorizations() {
  const t = useTranslations("authorizations");
  const [status, setStatus] = useState("");
  const q = useApiQuery<Authorization[]>(["sup-auths", status], "/supplier/authorizations", { status: status || undefined });
  return (
    <>
      <PageHeader title={t("title")} subtitle={t("supplier_subtitle")} actions={<Link href="/app/supplier/authorizations/new" className="inline-flex h-10 items-center gap-2 rounded-md bg-teal-500 px-4 text-sm font-semibold text-white"><Plus className="h-4 w-4" />{t("new")}</Link>} />
      <div className="mb-4"><Tabs value={status} onChange={setStatus} items={["", "sent", "pending_rep", "active", "suspended", "expired", "cancelled"].map((s) => ({ value: s, label: s ? t(`status.${s}`) : t("all") }))} /></div>
      <Card padded={false}><AuthorizationTable rows={q.data} loading={q.isLoading} side="supplier" /></Card>
    </>
  );
}
