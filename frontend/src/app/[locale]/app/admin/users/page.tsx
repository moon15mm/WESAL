"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { DataTable, Pagination, SearchInput, type Column } from "@/components/ui/data";
import { Badge, Card, PageHeader, StatusBadge } from "@/components/ui/layout";
import { ConfirmDialog } from "@/components/ui/overlay";
import { Button, Select } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { useFormat } from "@/lib/format";
import { useList } from "@/lib/list";
import { useApiAction } from "@/lib/useApiForm";

type U = { id: string; full_name: string; email: string | null; phone: string | null; status: string; mfa_enabled: boolean; last_login_at: string | null; roles: string[] };

export default function Users() {
  const t = useTranslations("admin");
  const f = useFormat();
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const list = useList<U>("/admin/users", { q, status });
  const [suspend, setSuspend] = useState<U | null>(null);
  const { loading, run } = useApiAction();
  const refresh = () => qc.invalidateQueries({ queryKey: ["/admin/users"] });
  const cols: Column<U>[] = [
    { key: "n", header: t("name"), cell: (u) => <span><span className="font-medium">{u.full_name}</span><span className="ltr block text-xs text-muted">{u.email || u.phone}</span></span> },
    { key: "r", header: t("roles"), cell: (u) => u.roles.map((r) => <Badge key={r} tone="navy">{r}</Badge>) },
    { key: "s", header: t("status"), cell: (u) => <StatusBadge status={u.status} /> },
    { key: "m", header: "MFA", hideOnMobile: true, cell: (u) => (u.mfa_enabled ? <Badge tone="success">✓</Badge> : "—") },
    { key: "l", header: t("last_login"), hideOnMobile: true, cell: (u) => f.datetime(u.last_login_at) },
    { key: "a", header: "", cell: (u) => u.status === "suspended" ? <Button size="sm" variant="outline" onClick={async () => { if (await run(() => api(`/admin/users/${u.id}/activate`, { method: "POST" }))) refresh(); }}>{t("activate")}</Button> : <Button size="sm" variant="ghost" className="text-danger" onClick={() => setSuspend(u)}>{t("suspend")}</Button> },
  ];
  return (
    <>
      <PageHeader title={t("users_title")} />
      <div className="mb-4 flex flex-col gap-3 sm:flex-row"><SearchInput value={q} onChange={(v) => { setQ(v); list.reset(); }} className="flex-1" /><Select value={status} onChange={(e) => setStatus(e.target.value)} className="sm:w-40">{["", "active", "pending", "suspended", "deleted"].map((s) => <option key={s} value={s}>{s ? t(`ustatus.${s}`) : t("all")}</option>)}</Select></div>
      <Card padded={false}><DataTable columns={cols} rows={list.data?.items} loading={list.isLoading} rowKey={(u) => u.id} />{list.data && <Pagination page={list.page} pageSize={list.pageSize} total={list.data.total} onPage={list.setPage} />}</Card>
      <ConfirmDialog open={!!suspend} onOpenChange={(v) => !v && setSuspend(null)} title={t("suspend")} requireReason tone="danger" loading={loading} onConfirm={async (reason) => { if (await run(() => api(`/admin/users/${suspend!.id}/suspend`, { body: { reason } }))) { setSuspend(null); refresh(); } }} />
    </>
  );
}
