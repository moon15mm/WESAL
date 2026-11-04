"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";
import { CommissionTable, type Commission } from "@/components/app/commissions";
import { Pagination, Tabs } from "@/components/ui/data";
import { Card, PageHeader, Stat } from "@/components/ui/layout";
import { useFormat } from "@/lib/format";
import { useList } from "@/lib/list";

export default function AdminCommissions() {
  const t = useTranslations("commissions");
  const f = useFormat();
  const [status, setStatus] = useState("");
  const list = useList<Commission>("/admin/commissions", { status });
  const s = (list.data?.summary || {}) as Record<string, { amount: string }>;
  return (
    <>
      <PageHeader title={t("title")} subtitle={t("admin_subtitle")} />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">{["estimated", "due", "paid", "disputed"].map((k) => <Stat key={k} label={t(`status.${k}`)} value={f.money(s[k]?.amount || 0)} />)}</div>
      <div className="my-4"><Tabs value={status} onChange={(x) => { setStatus(x); list.reset(); }} items={["", "estimated", "pending", "due", "approved", "paid", "disputed", "adjusted", "cancelled"].map((k) => ({ value: k, label: k ? t(`status.${k}`) : t("all") }))} /></div>
      <Card padded={false}><CommissionTable rows={list.data?.items} loading={list.isLoading} side="admin" />{list.data && <Pagination page={list.page} pageSize={list.pageSize} total={list.data.total} onPage={list.setPage} />}</Card>
    </>
  );
}
