"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";
import { DataTable, Pagination, SearchInput, type Column } from "@/components/ui/data";
import { Badge, Card, PageHeader } from "@/components/ui/layout";
import { Select } from "@/components/ui/primitives";
import { useFormat } from "@/lib/format";
import { useList } from "@/lib/list";

type A = { id: number; created_at: string; action: string; actor_user_id: string | null; entity_type: string | null; entity_id: string | null; result: string; reason: string | null; ip: string | null; changes: unknown };

export default function Audit() {
  const t = useTranslations("admin");
  const f = useFormat();
  const [action, setAction] = useState("");
  const [result, setResult] = useState("");
  const list = useList<A>("/admin/audit", { action, result }, 50);
  const cols: Column<A>[] = [
    { key: "d", header: t("date"), cell: (a) => <span className="whitespace-nowrap text-xs">{f.datetime(a.created_at)}</span> },
    { key: "a", header: t("action"), cell: (a) => <span className="ltr font-mono text-xs">{a.action}</span> },
    { key: "r", header: t("result"), cell: (a) => <Badge tone={a.result === "denied" ? "danger" : a.result === "failed" ? "warning" : "success"}>{a.result}</Badge> },
    { key: "e", header: t("entity"), hideOnMobile: true, cell: (a) => <span className="ltr text-xs">{a.entity_type}{a.entity_id && `:${a.entity_id.slice(0, 8)}`}</span> },
    { key: "u", header: t("actor"), hideOnMobile: true, cell: (a) => <span className="ltr font-mono text-xs">{a.actor_user_id?.slice(0, 8)}</span> },
    { key: "ip", header: "IP", hideOnMobile: true, cell: (a) => <span className="ltr text-xs">{a.ip}</span> },
    { key: "why", header: t("reason"), hideOnMobile: true, cell: (a) => <span className="text-xs">{a.reason}</span> },
  ];
  return (
    <>
      <PageHeader title={t("audit_title")} subtitle={t("audit_subtitle")} />
      <div className="mb-4 flex flex-col gap-3 sm:flex-row"><SearchInput value={action} onChange={(v) => { setAction(v); list.reset(); }} placeholder="order. / auth. / admin." className="flex-1" /><Select value={result} onChange={(e) => { setResult(e.target.value); list.reset(); }} className="sm:w-40"><option value="">{t("all")}</option><option value="success">success</option><option value="denied">denied</option><option value="failed">failed</option></Select></div>
      <Card padded={false}><DataTable columns={cols} rows={list.data?.items} loading={list.isLoading} rowKey={(a) => String(a.id)} />{list.data && <Pagination page={list.page} pageSize={list.pageSize} total={list.data.total} onPage={list.setPage} />}</Card>
    </>
  );
}
